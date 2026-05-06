from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

from app.models.analytics import ChatQueryEvent, QuestionCluster


STAT_TERMS = {
    "points": "pts",
    "point": "pts",
    "pts": "pts",
    "rebounds": "reb",
    "rebound": "reb",
    "reb": "reb",
    "assists": "ast",
    "assist": "ast",
    "ast": "ast",
    "turnovers": "tov",
    "turnover": "tov",
    "tov": "tov",
    "steals": "stl",
    "blocks": "blk",
    "field goal": "fg_pct",
    "three-point": "fg3_pct",
    "true shooting": "ts_pct",
    "effective field goal": "efg_pct",
    "fantasy": "fantasy_score",
}


def _query_specs(event: ChatQueryEvent) -> list[dict[str, Any]]:
    payload = event.analytics_payload or {}
    plan = payload.get("plan") or {}
    specs = []
    for step in plan.get("steps") or []:
        spec = (step.get("payload") or {}).get("query_spec")
        if isinstance(spec, dict):
            specs.append(spec)
    return specs


def _entities(event: ChatQueryEvent) -> list[dict[str, Any]]:
    payload = event.analytics_payload or {}
    entities = payload.get("entities") or []
    return entities if isinstance(entities, list) else []


def extract_stats(event: ChatQueryEvent) -> list[str]:
    stats: set[str] = set()
    for spec in _query_specs(event):
        aggregations = spec.get("aggregations") or {}
        if isinstance(aggregations, dict):
            stats.update(aggregations.keys())
        derived = spec.get("derived_metrics") or []
        if isinstance(derived, list):
            stats.update(derived)

    text = event.user_message.lower()
    for term, stat in STAT_TERMS.items():
        if term in text:
            stats.add(stat)
    return sorted(stats)


def extract_time_range(event: ChatQueryEvent) -> dict[str, Any]:
    text = event.user_message.lower()
    time_range: dict[str, Any] = {}
    season_match = re.search(r"(20\d{2})[-\u2013](\d{2})", text)
    if season_match:
        time_range["season"] = f"{season_match.group(1)}-{season_match.group(2)}"
    last_n = re.search(r"last\s+(\d+)", text)
    if last_n:
        time_range["last_n"] = int(last_n.group(1))
    if "regular season" in text:
        time_range["season_type"] = "regular season"
    if "playoff" in text:
        time_range["season_type"] = "playoffs"
    return time_range


def classify_intent(event: ChatQueryEvent) -> str:
    text = event.user_message.lower()
    specs = _query_specs(event)
    scopes = {spec.get("scope") for spec in specs}
    perspectives = {spec.get("perspective", "self") for spec in specs}
    stats = extract_stats(event)

    if event.chatbot_status == "needs_clarification":
        return "ambiguous"
    if any(word in text for word in ["compare", "versus", " vs "]):
        return "comparison"
    if any(word in text for word in ["most", "leader", "top", "rank"]):
        return "leaderboard"
    if "last" in text:
        return "last_n_games"
    if "opponent" in text or "against each" in text or "opponent" in perspectives:
        return "opponent_split"
    if any(metric in stats for metric in ["ts_pct", "efg_pct", "fg_pct", "fg3_pct", "fantasy_score"]):
        return "advanced_metric"
    if "team_game_stats" in scopes:
        return "team_stats"
    if "player_game_stats" in scopes:
        return "player_stats"
    if any(word in text for word in ["schedule", "next game", "when do"]):
        return "schedule"
    if "standing" in text or "record" in text:
        return "standings"
    return "general"


def classify_complexity(event: ChatQueryEvent) -> str:
    payload = event.analytics_payload or {}
    metadata = payload.get("execution_metadata") or {}
    step_count = metadata.get("step_count") or event.step_count or 0
    stats = extract_stats(event)
    if event.chatbot_status == "needs_clarification":
        return "ambiguous"
    if step_count > 1:
        return "multi_step"
    if classify_intent(event) in {"leaderboard", "comparison"}:
        return classify_intent(event)
    if any(stat.endswith("_pct") or stat in {"fantasy_score", "pra"} for stat in stats):
        return "derived_metric"
    if stats:
        return "aggregation"
    return "simple_lookup"


def extract_entities(event: ChatQueryEvent) -> dict[str, Any]:
    players = []
    teams = []
    for entity in _entities(event):
        entity_type = entity.get("entity_type")
        name = entity.get("resolved_name") or entity.get("surface_text")
        if not name:
            continue
        if entity_type == "player":
            players.append(name)
        elif entity_type == "team":
            teams.append(name)
    return {"raw": _entities(event), "players": players, "teams": teams}


def simple_embedding(text: str, dimensions: int = 64) -> list[float]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    counts = Counter(tokens)
    vector = [0.0] * dimensions
    for token, count in counts.items():
        idx = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % dimensions
        vector[idx] += float(count)
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [round(value / norm, 6) for value in vector]
    return vector


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def assign_cluster(session, event: ChatQueryEvent, embedding: list[float]) -> str | None:
    clusters = session.query(QuestionCluster).order_by(QuestionCluster.last_seen_at.desc()).limit(200).all()
    best_cluster = None
    best_score = 0.0
    for cluster in clusters:
        metadata = cluster.metadata_json or {}
        cluster_embedding = metadata.get("embedding")
        score = cosine_similarity(embedding, cluster_embedding)
        if score > best_score:
            best_cluster = cluster
            best_score = score

    if best_cluster and best_score >= 0.82:
        best_cluster.query_count += 1
        best_cluster.last_seen_at = datetime.utcnow()
        return best_cluster.id

    cluster = QuestionCluster(
        label=classify_intent(event),
        representative_question=event.user_message,
        metadata_json={"embedding": embedding},
    )
    session.add(cluster)
    session.flush()
    return cluster.id
