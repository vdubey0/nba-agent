from __future__ import annotations

from typing import Any

from app.models.analytics import ChatQueryEvent


def deterministic_outcome(event: ChatQueryEvent) -> tuple[str, str | None]:
    if event.http_status is not None and event.http_status >= 400:
        return "error", "http_error"
    if event.chatbot_status == "error":
        return "error", event.error_type or "chatbot_error"
    if event.chatbot_status == "needs_clarification":
        return "unverifiable", "needs_clarification"
    if not event.bot_response:
        return "error", "empty_response"

    payload: dict[str, Any] = event.analytics_payload or {}
    execution = payload.get("execution_result") or {}
    if execution.get("status") == "failed":
        return "error", "execution_failed"

    return "answered", None
