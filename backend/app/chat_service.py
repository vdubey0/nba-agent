from __future__ import annotations

import logging
import time
from typing import Any

from openai import OpenAI

from app.analytics.capture import record_chat_event
from app.chat_flow import answer_question, process_message
from app.db import SessionLocal


logger = logging.getLogger(__name__)


def _strip_private_fields(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    analytics_payload = result.pop("_analytics", None)
    return result, analytics_payload


def run_tracked_chat_message(
    *,
    client: OpenAI,
    message: str,
    conversation_id: str | None = None,
    include_steps: bool = False,
    source: str = "unknown",
    http_status: int | None = None,
    benchmark_run_id: str | None = None,
    benchmark_case_id: str | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    result = process_message(
        client=client,
        message=message,
        conversation_id=conversation_id,
        include_steps=include_steps,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    response, analytics_payload = _strip_private_fields(result)
    record_chat_event(
        source=source,
        user_message=message,
        result=response,
        latency_ms=latency_ms,
        http_status=http_status,
        analytics_payload=analytics_payload,
        benchmark_run_id=benchmark_run_id,
        benchmark_case_id=benchmark_case_id,
    )
    return response


def run_tracked_query(
    *,
    client: OpenAI,
    message: str,
    include_steps: bool = False,
    source: str = "unknown",
    http_status: int | None = None,
    benchmark_run_id: str | None = None,
    benchmark_case_id: str | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    session = SessionLocal()
    try:
        result = answer_question(
            client=client,
            session=session,
            message=message,
            include_steps=include_steps,
        )
    finally:
        session.close()

    latency_ms = (time.perf_counter() - started) * 1000
    response, analytics_payload = _strip_private_fields(result)
    record_chat_event(
        source=source,
        user_message=message,
        result=response,
        latency_ms=latency_ms,
        http_status=http_status,
        analytics_payload=analytics_payload,
        benchmark_run_id=benchmark_run_id,
        benchmark_case_id=benchmark_case_id,
    )
    return response
