from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.config import ANALYTICS_ENABLED, ANALYTICS_STORE_INTERMEDIATE_STEPS
from app.db import SessionLocal
from app.analytics.processor import process_event
from app.models.analytics import AnalyticsJob, ChatQueryEvent


logger = logging.getLogger(__name__)


def _error_message(error: Any) -> str | None:
    if not error:
        return None
    if isinstance(error, dict):
        return error.get("message") or error.get("details") or str(error)
    return str(error)


def _error_type(result: dict[str, Any], http_status: int | None) -> str | None:
    if http_status is not None and http_status >= 400:
        return "http_error"
    status = result.get("status")
    if status == "error":
        return "chatbot_error"
    if status == "needs_clarification":
        return "needs_clarification"
    return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def record_chat_event(
    *,
    source: str,
    user_message: str,
    result: dict[str, Any],
    latency_ms: float | None,
    http_status: int | None = None,
    analytics_payload: dict[str, Any] | None = None,
    benchmark_run_id: str | None = None,
    benchmark_case_id: str | None = None,
) -> str | None:
    if not ANALYTICS_ENABLED:
        return None

    session = SessionLocal()
    try:
        payload = analytics_payload or result.get("_analytics") or {}
        execution_metadata = result.get("execution_metadata") or payload.get("execution_metadata") or {}
        plan = result.get("plan") or payload.get("plan") or {}
        intermediate_steps = result.get("intermediate_steps")
        if not ANALYTICS_STORE_INTERMEDIATE_STEPS:
            intermediate_steps = None

        event = ChatQueryEvent(
            conversation_id=result.get("conversation_id"),
            source=source,
            user_message=user_message,
            bot_response=result.get("response"),
            chatbot_status=result.get("status"),
            http_status=http_status,
            latency_ms=latency_ms,
            plan_type=plan.get("plan_type") if isinstance(plan, dict) else None,
            step_count=execution_metadata.get("step_count"),
            result_row_count=execution_metadata.get("result_row_count"),
            intermediate_steps=_json_safe(intermediate_steps),
            analytics_payload=_json_safe(payload),
            error_type=_error_type(result, http_status),
            error_message=_error_message(result.get("error")),
            benchmark_run_id=benchmark_run_id,
            benchmark_case_id=benchmark_case_id,
        )
        session.add(event)
        session.flush()
        session.commit()
        event_id = event.id

        try:
            event = session.query(ChatQueryEvent).filter(ChatQueryEvent.id == event_id).one()
            process_event(session, event, allow_llm_claim_extraction=False)
            job = AnalyticsJob(
                query_event_id=event_id,
                job_type="process_chat_event",
                status="completed",
                completed_at=datetime.utcnow(),
            )
            session.add(job)
            session.commit()
        except Exception as exc:
            session.rollback()
            job = AnalyticsJob(
                query_event_id=event_id,
                job_type="process_chat_event",
                status="retrying",
                last_error=repr(exc),
            )
            session.add(job)
            session.commit()
            logger.exception("Failed to process analytics event inline")

        return event_id
    except Exception:
        session.rollback()
        logger.exception("Failed to record analytics event")
        return None
    finally:
        session.close()
