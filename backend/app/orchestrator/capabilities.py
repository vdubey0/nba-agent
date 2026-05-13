from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class PlannerCapability:
    capability_id: str
    plan_type: str
    description: str
    cues: tuple[str, ...]
    planning_hints: tuple[str, ...]
    examples: tuple[str, ...] = ()


CAPABILITIES: tuple[PlannerCapability, ...] = (
    PlannerCapability(
        capability_id="single_query",
        plan_type="single_query",
        description="One dataset can answer the question with no intermediate dependency.",
        cues=("average", "averages", "allow the most", "force the most", "least"),
        planning_hints=(
            "Use a single query step when one query_spec can answer the full question.",
            "For league-wide rankings, use subject.type = league.",
        ),
        examples=(
            "What does Steph Curry average this season?",
            "Which teams force the most turnovers?",
        ),
    ),
    PlannerCapability(
        capability_id="multi_leaderboard",
        plan_type="multi_leaderboard",
        description="Multiple independent rankings over the same population.",
        cues=("scores, rebounds", "points, rebounds", "rebounds, assists", "leaderboards"),
        planning_hints=(
            "Use one independent query step per ranking dimension.",
            "Keep filters and grouping consistent, changing only the sort field when possible.",
        ),
        examples=("Who scores, rebounds, and assists the most against the Warriors?",),
    ),
    PlannerCapability(
        capability_id="derived_cohort",
        plan_type="derived_cohort",
        description="A ranked cohort is defined first, then another entity is analyzed against that cohort.",
        cues=("top", "bottom", "best", "worst", "teams that", "players that"),
        planning_hints=(
            "Use query -> extract_ids -> query -> filter_rows for cohort questions.",
            "Do not collapse cohort questions into a single query_spec.",
        ),
        examples=("How does Steph Curry play against the 10 teams that force the most turnovers?",),
    ),
    PlannerCapability(
        capability_id="team_record",
        plan_type="multi_query",
        description="Team record questions need separate win and loss counts.",
        cues=("record", "wins and losses", "without", "with"),
        planning_hints=(
            "For a team record, create separate win and loss query steps.",
            "For record without a player, include absent_player_ids in both steps.",
        ),
        examples=("What is the Warriors record this season without Steph Curry?",),
    ),
    PlannerCapability(
        capability_id="season_high_vs_team",
        plan_type="multi_query",
        description="Compare season maximums with maximums against a specific opponent.",
        cues=("season high", "career high", "scored their", "vs"),
        planning_hints=(
            "Compare an all-season max query with an opponent-specific max query.",
            "The synthesis step can identify rows where the max values match.",
        ),
        examples=("Which players scored their season high vs the Warriors this season?",),
    ),
    PlannerCapability(
        capability_id="all_players_in_team_game",
        plan_type="multi_query",
        description="Questions about all players in one team game need self and opponent player rows.",
        cues=("last", "game", "who scored", "most points"),
        planning_hints=(
            "For all players in a team's game, query team players with perspective self and opponent players with perspective opponent.",
            "Do not add sort or limit when the synthesis step must compare both teams.",
        ),
        examples=("Who scored the most points in the last Lakers game?",),
    ),
    PlannerCapability(
        capability_id="playoff_series_game_number",
        plan_type="single_query",
        description="Playoff Game X means the Xth chronological game of a playoff matchup or series.",
        cues=("game 1", "game 2", "game 3", "game 4", "game 5", "game 6", "game 7", "series"),
        planning_hints=(
            "For playoff Game X, use season_type = ['Playoffs'], the matchup opponent_team_id, sort by game_date ascending, and limit X.",
            "Do not use last_n_games for Game X, and do not aggregate; return raw rows so synthesis can select the Xth game.",
        ),
        examples=("What happened in Game 4 of Warriors vs Lakers?",),
    ),
    PlannerCapability(
        capability_id="advanced_metric",
        plan_type="single_query",
        description="Advanced and derived metrics need their component aggregations.",
        cues=("usage rate", "true shooting", "effective field goal", "fantasy", "net rating"),
        planning_hints=(
            "When using derived_metrics, include the required component stats in aggregations.",
            "Sort by the derived metric name when ranking derived metrics.",
        ),
        examples=("Which Warriors players have the highest usage rate in the last 10 games?",),
    ),
    PlannerCapability(
        capability_id="conditional_player_stats",
        plan_type="single_query",
        description="Player performance conditioned on another team's game context.",
        cues=("when", "wins", "win by", "losses", "in games where"),
        planning_hints=(
            "Interpret team win/loss conditions from the relevant game context, not as team membership for the player.",
            "Use filters that represent the condition while keeping the requested player as the subject.",
        ),
        examples=("In games where the Raptors win by 10 or more points, how much fantasy score does Brandon Ingram average?",),
    ),
)


def matched_capabilities(question: str, limit: int = 3) -> list[PlannerCapability]:
    normalized = question.lower()
    scored: list[tuple[int, PlannerCapability]] = []

    for capability in CAPABILITIES:
        score = 0
        for cue in capability.cues:
            cue_normalized = cue.lower()
            if " " in cue_normalized:
                if cue_normalized in normalized:
                    score += 2
            elif re.search(rf"\b{re.escape(cue_normalized)}\b", normalized):
                score += 1
        if score:
            scored.append((score, capability))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [capability for _, capability in scored[:limit]]


def capability_context(question: str) -> dict[str, Any]:
    matches = matched_capabilities(question)
    return {
        "matched_capabilities": [
            {
                "capability_id": capability.capability_id,
                "plan_type": capability.plan_type,
                "description": capability.description,
                "planning_hints": list(capability.planning_hints),
                "examples": list(capability.examples),
            }
            for capability in matches
        ],
        "fallback": "Use the full universal planning rules when no capability hint is decisive.",
    }


def format_capability_context(question: str) -> str:
    context = capability_context(question)
    matches = context["matched_capabilities"]
    if not matches:
        return ""

    lines = [
        "",
        "==================================================",
        "RELEVANT CAPABILITY HINTS",
        "==================================================",
        "These hints are advisory. If they conflict with the full planning contract, follow the full contract.",
    ]
    for match in matches:
        lines.append(f"- {match['capability_id']} ({match['plan_type']}): {match['description']}")
        for hint in match["planning_hints"]:
            lines.append(f"  - {hint}")
    return "\n".join(lines)
