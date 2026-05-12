from __future__ import annotations

import logging
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.config import ANALYTICS_ENABLED, ANALYTICS_STORE_INTERMEDIATE_STEPS
from app.db import SessionLocal
from app.models.analytics import AnalyticsJob, ChatQueryEvent


logger = logging.getLogger(__name__)


def _error_message(error: Any) -> str | None:
    if not error:
        return None
    if isinstance(error, dict):
        message = error.get("message")
        details = error.get("details")
        if details is None:
            return message or str(error)

        if isinstance(details, (dict, list)):
            details_text = json.dumps(_json_safe(details), sort_keys=True)
        else:
            details_text = str(details)

        if message and details_text and details_text != message:
            return f"{message}\n\nDetails: {details_text}"
        return message or details_text
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
        llm_usage = result.get("llm_usage") or payload.get("llm_usage") or {}
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
            model_name=llm_usage.get("model_name"),
            prompt_tokens=llm_usage.get("prompt_tokens"),
            completion_tokens=llm_usage.get("completion_tokens"),
            total_tokens=llm_usage.get("total_tokens"),
            estimated_cost=llm_usage.get("estimated_cost"),
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
        event_id = event.id

        job = AnalyticsJob(
            query_event_id=event_id,
            job_type="process_chat_event",
            status="pending",
        )
        session.add(job)
        session.commit()

        return event_id
    except Exception:
        session.rollback()
        logger.exception("Failed to record analytics event")
        return None
    finally:
        session.close()
