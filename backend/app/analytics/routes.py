from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, and_, cast, func, not_, or_
from sqlalchemy.orm import Session

from app.analytics.classification import classify_complexity, classify_intent, extract_entities, extract_stats, extract_time_range
from app.analytics.evaluation import llm_review_answer
from app.analytics.outcome import deterministic_outcome
from app.db import SessionLocal
from app.models.analytics import (
    AnalyticsJob,
    ChatEvaluation,
    ChatQueryEvent,
    ChatQuestionAnalysis,
    QuestionCluster,
)


router = APIRouter(prefix="/admin/api/analytics", tags=["analytics"])


OPENAI_QUOTA_ERROR_MARKERS = (
    "insufficient_quota",
    "exceeded your current quota",
)


class ApplyReviewRequest(BaseModel):
    outcome: str
    reviewer: str | None = "user"
    llm_review: dict[str, Any] | None = None


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    index = (len(sorted_values) - 1) * percentile
    lower_index = int(index)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = index - lower_index
    return sorted_values[lower_index] + (sorted_values[upper_index] - sorted_values[lower_index]) * fraction


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _date_window(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


def _base_events(session: Session, days: int, source: str | None = None):
    query = session.query(ChatQueryEvent).filter(ChatQueryEvent.created_at >= _date_window(days))
    if source == "query_family":
        query = query.filter(ChatQueryEvent.source.in_(["api_query", "seed_api_query", "debug_api_query"]))
    elif source == "local_family":
        query = query.filter(ChatQueryEvent.source.in_(["api_chat", "interactive_chat", "agent_flow", "seed_local_query"]))
    elif source:
        query = query.filter(ChatQueryEvent.source == source)
    return query


def _openai_quota_error_clause():
    error_message = func.coalesce(ChatQueryEvent.error_message, "")
    payload_text = func.coalesce(cast(ChatQueryEvent.analytics_payload, String), "")
    return or_(
        *[
            error_message.ilike(f"%{marker}%")
            for marker in OPENAI_QUOTA_ERROR_MARKERS
        ],
        *[
            payload_text.ilike(f"%{marker}%")
            for marker in OPENAI_QUOTA_ERROR_MARKERS
        ],
    )


def _dashboard_events(session: Session, days: int, source: str | None = None):
    return _base_events(session, days, source).filter(not_(_openai_quota_error_clause()))


def _hour_bucket(value: datetime | None) -> str:
    if not value:
        return "unknown"
    return value.replace(minute=0, second=0, microsecond=0).isoformat()


def _empty_cluster_rollup(label: str) -> dict[str, Any]:
    return {
        "id": label,
        "label": label,
        "representative_question": "",
        "query_count": 0,
        "last_seen_at": None,
        "questions": [],
        "hourly_demand": defaultdict(int),
        "source_breakdown": defaultdict(int),
        "outcome_breakdown": defaultdict(int),
        "correct_count": 0,
        "verifiable_count": 0,
        "error_count": 0,
        "latency_total_ms": 0.0,
        "cluster_ids": set(),
    }


def _finalize_cluster_rollup(item: dict[str, Any]) -> dict[str, Any]:
    query_count = item["query_count"]
    avg_latency = item["latency_total_ms"] / query_count if query_count else 0
    return {
        "id": item["id"],
        "label": item["label"],
        "representative_question": item["representative_question"],
        "query_count": query_count,
        "last_seen_at": item["last_seen_at"].isoformat() if item["last_seen_at"] else None,
        "accuracy_rate": round(item["correct_count"] / item["verifiable_count"], 4) if item["verifiable_count"] else 0,
        "error_rate": round(item["error_count"] / query_count, 4) if query_count else 0,
        "avg_latency_ms": round(avg_latency, 2),
        "source_breakdown": [
            {"source": source, "query_count": count}
            for source, count in sorted(item["source_breakdown"].items(), key=lambda row: row[1], reverse=True)
        ],
        "outcome_breakdown": [
            {"outcome": outcome, "query_count": count}
            for outcome, count in sorted(item["outcome_breakdown"].items(), key=lambda row: row[1], reverse=True)
        ],
        "hourly_demand": [
            {"hour": hour, "query_count": count}
            for hour, count in sorted(item["hourly_demand"].items())
        ],
        "questions": item["questions"],
        "cluster_ids": sorted(item["cluster_ids"]),
    }


@router.get("/summary")
def analytics_summary(
    days: int = Query(30, ge=1, le=365),
    source: str | None = None,
    session: Session = Depends(get_session),
):
    events = _dashboard_events(session, days, source)
    total = events.count()
    avg_latency = events.with_entities(func.avg(ChatQueryEvent.latency_ms)).scalar() or 0
    error_count = (
        events.join(ChatEvaluation, ChatEvaluation.query_event_id == ChatQueryEvent.id, isouter=True)
        .filter(
            or_(
                ChatEvaluation.outcome == "error",
                ChatEvaluation.is_error.is_(True),
                ChatQueryEvent.error_type.isnot(None),
            )
        )
        .count()
    )
    correct_count = (
        events.join(ChatEvaluation, ChatEvaluation.query_event_id == ChatQueryEvent.id, isouter=True)
        .filter(ChatEvaluation.outcome == "correct")
        .count()
    )
    verifiable_count = (
        events.join(ChatEvaluation, ChatEvaluation.query_event_id == ChatQueryEvent.id, isouter=True)
        .filter(ChatEvaluation.is_verifiable.is_(True))
        .count()
    )
    pending_jobs = session.query(AnalyticsJob).filter(AnalyticsJob.status.in_(["pending", "retrying", "processing"])).count()

    return {
        "total_queries": total,
        "average_latency_ms": round(float(avg_latency), 2),
        "error_rate": round(error_count / total, 4) if total else 0,
        "objective_accuracy_rate": round(correct_count / verifiable_count, 4) if verifiable_count else 0,
        "verifiable_count": verifiable_count,
        "pending_jobs": pending_jobs,
    }


@router.get("/latency-distribution")
def analytics_latency_distribution(
    days: int = Query(30, ge=1, le=365),
    source: str | None = None,
    session: Session = Depends(get_session),
):
    rows = (
        _dashboard_events(session, days, source)
        .join(ChatEvaluation, ChatEvaluation.query_event_id == ChatQueryEvent.id, isouter=True)
        .filter(ChatQueryEvent.latency_ms.isnot(None))
        .filter(ChatQueryEvent.error_type.is_(None))
        .filter(or_(ChatEvaluation.id.is_(None), and_(ChatEvaluation.outcome != "error", ChatEvaluation.is_error.is_(False))))
        .with_entities(ChatQueryEvent.latency_ms)
        .all()
    )
    values = sorted(float(row[0]) for row in rows if row[0] is not None)
    percentiles = {
        "p25": _percentile(values, 0.25),
        "p50": _percentile(values, 0.50),
        "p75": _percentile(values, 0.75),
        "p95": _percentile(values, 0.95),
        "p99": _percentile(values, 0.99),
    }
    return {
        "count": len(values),
        "min_ms": round(values[0], 2) if values else 0,
        "max_ms": round(values[-1], 2) if values else 0,
        **{key: round(value, 2) for key, value in percentiles.items()},
    }


@router.get("/performance")
def analytics_performance(
    days: int = Query(30, ge=1, le=365),
    source: str | None = None,
    session: Session = Depends(get_session),
):
    events = _dashboard_events(session, days, source)
    by_day = (
        events.with_entities(
            func.date(ChatQueryEvent.created_at).label("day"),
            func.count(ChatQueryEvent.id),
            func.avg(ChatQueryEvent.latency_ms),
            func.max(ChatQueryEvent.latency_ms),
        )
        .group_by(func.date(ChatQueryEvent.created_at))
        .order_by(func.date(ChatQueryEvent.created_at))
        .all()
    )
    by_source = (
        events.with_entities(ChatQueryEvent.source, func.count(ChatQueryEvent.id), func.avg(ChatQueryEvent.latency_ms))
        .group_by(ChatQueryEvent.source)
        .order_by(func.count(ChatQueryEvent.id).desc())
        .all()
    )
    source_totals: dict[str, dict[str, Any]] = {}
    for item_source, count, avg in by_source:
        label = _source_label(item_source)
        bucket = source_totals.setdefault(label, {"source": label, "query_count": 0, "latency_total": 0.0})
        bucket["query_count"] += count
        bucket["latency_total"] += float(avg or 0) * count

    slowest = events.order_by(ChatQueryEvent.latency_ms.desc()).limit(10).all()
    return {
        "by_day": [
            {
                "day": str(day),
                "query_count": count,
                "avg_latency_ms": round(float(avg or 0), 2),
                "max_latency_ms": round(float(max_latency or 0), 2),
            }
            for day, count, avg, max_latency in by_day
        ],
        "by_source": [
            {
                "source": item["source"],
                "query_count": item["query_count"],
                "avg_latency_ms": round(item["latency_total"] / item["query_count"], 2) if item["query_count"] else 0,
            }
            for item in sorted(source_totals.values(), key=lambda row: row["query_count"], reverse=True)
        ],
        "slowest": [_event_summary(event) for event in slowest],
    }


@router.get("/accuracy")
def analytics_accuracy(
    days: int = Query(30, ge=1, le=365),
    source: str | None = None,
    session: Session = Depends(get_session),
):
    events = _dashboard_events(session, days, source).subquery()
    outcome_rows = (
        session.query(ChatQueryEvent, ChatEvaluation)
        .join(ChatEvaluation, ChatEvaluation.query_event_id == ChatQueryEvent.id)
        .join(events, events.c.id == ChatQueryEvent.id)
        .all()
    )
    outcome_counts: dict[str, int] = {}
    for event, evaluation in outcome_rows:
        outcome = _display_outcome(event, evaluation)
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

    by_intent = (
        session.query(
            ChatQuestionAnalysis.intent_category,
            ChatEvaluation.outcome,
            func.count(ChatEvaluation.id),
        )
        .join(events, events.c.id == ChatQuestionAnalysis.query_event_id)
        .join(ChatEvaluation, ChatEvaluation.query_event_id == ChatQuestionAnalysis.query_event_id)
        .group_by(ChatQuestionAnalysis.intent_category, ChatEvaluation.outcome)
        .all()
    )
    review_queue = (
        session.query(ChatQueryEvent, ChatEvaluation, ChatQuestionAnalysis)
        .join(ChatEvaluation, ChatEvaluation.query_event_id == ChatQueryEvent.id)
        .join(ChatQuestionAnalysis, ChatQuestionAnalysis.query_event_id == ChatQueryEvent.id, isouter=True)
        .join(events, events.c.id == ChatQueryEvent.id)
        .filter(ChatEvaluation.outcome.in_(["unverifiable", "incorrect"]))
        .filter(ChatQueryEvent.error_type.is_(None))
        .filter(
            or_(
                ChatEvaluation.evaluation_method.is_(None),
                ChatEvaluation.evaluation_method != "llm_assisted_manual_review",
            )
        )
        .order_by(ChatQueryEvent.created_at.desc())
        .limit(25)
        .all()
    )
    errors = (
        session.query(ChatQueryEvent, ChatEvaluation, ChatQuestionAnalysis)
        .join(ChatEvaluation, ChatEvaluation.query_event_id == ChatQueryEvent.id)
        .join(ChatQuestionAnalysis, ChatQuestionAnalysis.query_event_id == ChatQueryEvent.id, isouter=True)
        .join(events, events.c.id == ChatQueryEvent.id)
        .filter(
            or_(
                ChatEvaluation.outcome == "error",
                ChatEvaluation.is_error.is_(True),
                ChatQueryEvent.error_type.isnot(None),
                and_(
                    ChatEvaluation.outcome == "incorrect",
                    ChatEvaluation.evaluation_method == "llm_assisted_manual_review",
                ),
            )
        )
        .order_by(ChatQueryEvent.created_at.desc())
        .limit(25)
        .all()
    )
    return {
        "outcomes": [{"outcome": outcome, "count": count} for outcome, count in sorted(outcome_counts.items())],
        "by_intent": [
            {"intent": intent or "unknown", "outcome": outcome or "pending", "count": count}
            for intent, outcome, count in by_intent
        ],
        "review_queue": [
            {
                **_event_summary(event),
                "outcome": _display_outcome(event, evaluation),
                "mismatches": evaluation.mismatches,
                "intent": analysis.intent_category if analysis else None,
            }
            for event, evaluation, analysis in review_queue
        ],
        "errors": [
            {
                **_event_summary(event),
                "outcome": _display_outcome(event, evaluation),
                "mismatches": evaluation.mismatches,
                "intent": analysis.intent_category if analysis else None,
            }
            for event, evaluation, analysis in errors
        ],
    }


@router.get("/questions")
def analytics_questions(
    days: int = Query(30, ge=1, le=365),
    source: str | None = None,
    session: Session = Depends(get_session),
):
    events = _dashboard_events(session, days, source).subquery()
    intents = (
        session.query(ChatQuestionAnalysis.intent_category, func.count(ChatQuestionAnalysis.id), func.avg(ChatQueryEvent.latency_ms))
        .join(events, events.c.id == ChatQuestionAnalysis.query_event_id)
        .join(ChatQueryEvent, ChatQueryEvent.id == ChatQuestionAnalysis.query_event_id)
        .group_by(ChatQuestionAnalysis.intent_category)
        .order_by(func.count(ChatQuestionAnalysis.id).desc())
        .all()
    )
    complexity = (
        session.query(ChatQuestionAnalysis.complexity_type, func.count(ChatQuestionAnalysis.id), func.avg(ChatQueryEvent.latency_ms))
        .join(events, events.c.id == ChatQuestionAnalysis.query_event_id)
        .join(ChatQueryEvent, ChatQueryEvent.id == ChatQuestionAnalysis.query_event_id)
        .group_by(ChatQuestionAnalysis.complexity_type)
        .order_by(func.count(ChatQuestionAnalysis.id).desc())
        .all()
    )
    cluster_rows = (
        session.query(ChatQueryEvent, ChatQuestionAnalysis, QuestionCluster, ChatEvaluation)
        .join(ChatQuestionAnalysis, ChatQuestionAnalysis.query_event_id == ChatQueryEvent.id)
        .join(QuestionCluster, QuestionCluster.id == ChatQuestionAnalysis.cluster_id)
        .join(ChatEvaluation, ChatEvaluation.query_event_id == ChatQueryEvent.id, isouter=True)
        .join(events, events.c.id == ChatQueryEvent.id)
        .order_by(ChatQueryEvent.created_at.desc())
        .all()
    )
    cluster_rollups: dict[str, dict[str, Any]] = {}
    for event, analysis, cluster, evaluation in cluster_rows:
        label = cluster.label or analysis.intent_category or "unknown"
        cluster_key = label.lower()
        item = cluster_rollups.setdefault(cluster_key, _empty_cluster_rollup(label))
        outcome = _display_outcome(event, evaluation)
        source_label = _source_label(event.source)

        item["query_count"] += 1
        item["latency_total_ms"] += float(event.latency_ms or 0)
        item["source_breakdown"][source_label] += 1
        item["outcome_breakdown"][outcome] += 1
        item["hourly_demand"][_hour_bucket(event.created_at)] += 1
        item["cluster_ids"].add(cluster.id)
        if outcome == "correct":
            item["correct_count"] += 1
        if outcome in {"correct", "incorrect"}:
            item["verifiable_count"] += 1
        if outcome == "error":
            item["error_count"] += 1
        if not item["last_seen_at"] or event.created_at > item["last_seen_at"]:
            item["last_seen_at"] = event.created_at
            item["representative_question"] = cluster.representative_question or event.user_message

        item["questions"].append(
            {
                "id": event.id,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "question": event.user_message,
                "source": source_label,
                "outcome": outcome,
                "latency_ms": round(float(event.latency_ms or 0), 2),
            }
        )

    clusters = sorted(
        (_finalize_cluster_rollup(item) for item in cluster_rollups.values()),
        key=lambda item: item["query_count"],
        reverse=True,
    )[:20]
    recent = _dashboard_events(session, days, source).order_by(ChatQueryEvent.created_at.desc()).limit(50).all()
    return {
        "intents": [
            {"intent": intent or "unknown", "query_count": count, "avg_latency_ms": round(float(avg or 0), 2)}
            for intent, count, avg in intents
        ],
        "complexity": [
            {"complexity": item or "unknown", "query_count": count, "avg_latency_ms": round(float(avg or 0), 2)}
            for item, count, avg in complexity
        ],
        "clusters": clusters,
        "recent_events": [_event_summary(event) for event in recent],
    }


@router.get("/events")
def analytics_events(
    days: int = Query(30, ge=1, le=365),
    source: str | None = None,
    outcome: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    query = (
        _dashboard_events(session, days, source)
        .join(ChatEvaluation, ChatEvaluation.query_event_id == ChatQueryEvent.id, isouter=True)
        .join(ChatQuestionAnalysis, ChatQuestionAnalysis.query_event_id == ChatQueryEvent.id, isouter=True)
    )
    if outcome:
        query = query.filter(ChatEvaluation.outcome == outcome)
    rows = query.order_by(ChatQueryEvent.created_at.desc()).limit(limit).all()
    return {"events": [_event_summary(event) for event in rows]}


@router.get("/events/{event_id}")
def analytics_event_detail(event_id: str, session: Session = Depends(get_session)):
    event = session.query(ChatQueryEvent).filter(ChatQueryEvent.id == event_id).one()
    summary = _event_summary(event)
    return {
        **summary,
        "bot_response": event.bot_response,
        "intermediate_steps": event.intermediate_steps,
        "analytics_payload": event.analytics_payload,
        "evaluation": _evaluation_summary(event.evaluation),
        "question_analysis": summary["question_analysis"],
    }


@router.post("/events/{event_id}/automatic-review")
def automatic_review(event_id: str, session: Session = Depends(get_session)):
    event = session.query(ChatQueryEvent).filter(ChatQueryEvent.id == event_id).one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Analytics event not found")

    try:
        review = llm_review_answer(event)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Automatic review failed: {exc}") from exc

    return {
        "event": {**_event_summary(event), "bot_response": event.bot_response},
        "review": review,
    }


@router.post("/events/{event_id}/apply-review")
def apply_review(event_id: str, request: ApplyReviewRequest, session: Session = Depends(get_session)):
    outcome = request.outcome.strip().lower()
    if outcome not in {"correct", "incorrect"}:
        raise HTTPException(status_code=400, detail="Outcome must be correct or incorrect")

    event = session.query(ChatQueryEvent).filter(ChatQueryEvent.id == event_id).one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Analytics event not found")

    evaluation = event.evaluation
    if not evaluation:
        evaluation = ChatEvaluation(query_event_id=event.id)
        session.add(evaluation)

    previous = _evaluation_summary(evaluation)
    stored_outcome = "error" if outcome == "incorrect" and (event.error_type or not event.bot_response) else outcome

    evaluation.evaluation_status = "completed"
    evaluation.outcome = stored_outcome
    evaluation.is_error = stored_outcome == "error"
    evaluation.is_verifiable = stored_outcome in {"correct", "incorrect"}
    evaluation.is_correct = True if stored_outcome == "correct" else False if stored_outcome == "incorrect" else None
    evaluation.evaluation_method = "llm_assisted_manual_review"
    evaluation.mismatches = {
        "reviewer": request.reviewer or "user",
        "previous_evaluation": previous,
        "llm_review": request.llm_review,
    }
    evaluation.created_at = datetime.utcnow()
    (
        session.query(AnalyticsJob)
        .filter(AnalyticsJob.query_event_id == event.id)
        .filter(AnalyticsJob.status.in_(["pending", "retrying"]))
        .update(
            {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "last_error": None,
            },
            synchronize_session=False,
        )
    )
    session.commit()
    session.refresh(event)

    return {
        "event": _event_summary(event),
        "evaluation": _evaluation_summary(event.evaluation),
    }


def _display_outcome(event: ChatQueryEvent, evaluation: ChatEvaluation | None) -> str:
    if event.error_type or evaluation and evaluation.is_error:
        return "error"
    if evaluation and evaluation.outcome == "incorrect" and evaluation.evaluation_method != "llm_assisted_manual_review":
        return "unverifiable"
    if evaluation and evaluation.outcome:
        return evaluation.outcome
    return "pending"


def _source_label(source: str | None) -> str:
    if source in {"api_query", "seed_api_query", "debug_api_query"}:
        return "/query"
    if source in {"api_chat", "interactive_chat", "agent_flow", "seed_local_query"}:
        return "local chat"
    return source or "unknown"


def _event_summary(event: ChatQueryEvent) -> dict[str, Any]:
    display_outcome = _display_outcome(event, event.evaluation)
    evaluation = _evaluation_summary(event.evaluation, display_outcome)
    if not evaluation:
        outcome, _ = deterministic_outcome(event)
        display_outcome = outcome
        evaluation = {
            "status": "inferred",
            "outcome": display_outcome,
            "is_verifiable": False,
            "is_correct": None,
            "mismatches": None,
            "expected_values": None,
            "extracted_values": None,
            "evaluation_method": "deterministic_outcome_fallback",
        }

    question_analysis = _analysis_summary(event.question_analysis)
    if not question_analysis or question_analysis.get("intent_category") == "error":
        entities = extract_entities(event)
        question_analysis = {
            "intent_category": classify_intent(event),
            "players": entities["players"],
            "teams": entities["teams"],
            "stats": extract_stats(event),
            "time_range": extract_time_range(event),
            "complexity_type": classify_complexity(event),
            "cluster_id": None,
        }

    return {
        "id": event.id,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "source": _source_label(event.source),
        "conversation_id": event.conversation_id,
        "user_message": event.user_message,
        "bot_response_preview": (event.bot_response or "")[:180],
        "chatbot_status": event.chatbot_status,
        "latency_ms": round(float(event.latency_ms or 0), 2),
        "plan_type": event.plan_type,
        "step_count": event.step_count,
        "result_row_count": event.result_row_count,
        "error_type": event.error_type,
        "error_message": _event_error_message(event),
        "evaluation": evaluation,
        "question_analysis": question_analysis,
    }


def _event_error_message(event: ChatQueryEvent) -> str | None:
    if event.error_message:
        payload_error = (event.analytics_payload or {}).get("error")
        details = payload_error.get("details") if isinstance(payload_error, dict) else None
        if (
            details
            and event.error_message == "An unexpected error occurred"
            and str(details) != event.error_message
        ):
            return f"{event.error_message}\n\nDetails: {details}"
        return event.error_message

    payload_error = (event.analytics_payload or {}).get("error")
    if isinstance(payload_error, dict):
        message = payload_error.get("message")
        details = payload_error.get("details")
        if message and details and str(details) != message:
            return f"{message}\n\nDetails: {details}"
        return message or (str(details) if details else None)
    if payload_error:
        return str(payload_error)
    return None


def _evaluation_summary(evaluation: ChatEvaluation | None, display_outcome: str | None = None) -> dict[str, Any] | None:
    if not evaluation:
        return None
    return {
        "status": evaluation.evaluation_status,
        "outcome": display_outcome or evaluation.outcome,
        "is_verifiable": evaluation.is_verifiable,
        "is_correct": evaluation.is_correct,
        "mismatches": evaluation.mismatches,
        "expected_values": evaluation.expected_values,
        "extracted_values": evaluation.extracted_values,
        "evaluation_method": evaluation.evaluation_method,
    }


def _analysis_summary(analysis: ChatQuestionAnalysis | None) -> dict[str, Any] | None:
    if not analysis:
        return None
    return {
        "intent_category": analysis.intent_category,
        "players": analysis.players,
        "teams": analysis.teams,
        "stats": analysis.stats,
        "time_range": analysis.time_range,
        "complexity_type": analysis.complexity_type,
        "cluster_id": analysis.cluster_id,
    }
