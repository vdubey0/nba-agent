from __future__ import annotations

from contextvars import ContextVar
from typing import Any


MODEL_PRICES_PER_1M = {
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
    "gpt-5.4-nano": {"input": 0.20, "cached_input": 0.02, "output": 1.25},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
}

_usage_events: ContextVar[list[dict[str, Any]] | None] = ContextVar("llm_usage_events", default=None)


def start_usage_tracking() -> None:
    _usage_events.set([])


def current_usage_events() -> list[dict[str, Any]]:
    return list(_usage_events.get() or [])


def _get_usage_value(usage: Any, *names: str) -> int:
    for name in names:
        if isinstance(usage, dict):
            value = usage.get(name)
        else:
            value = getattr(usage, name, None)
        if value is not None:
            return int(value)
    return 0


def _cached_input_tokens(usage: Any) -> int:
    details = None
    if isinstance(usage, dict):
        details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details")
    else:
        details = getattr(usage, "input_tokens_details", None) or getattr(usage, "prompt_tokens_details", None)

    if isinstance(details, dict):
        return int(details.get("cached_tokens") or 0)
    if details is not None:
        return int(getattr(details, "cached_tokens", 0) or 0)
    return 0


def estimate_cost(model: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float | None:
    prices = MODEL_PRICES_PER_1M.get(model)
    if not prices:
        return None

    billable_input = max(input_tokens - cached_input_tokens, 0)
    cost = (
        billable_input * prices["input"]
        + cached_input_tokens * prices["cached_input"]
        + output_tokens * prices["output"]
    ) / 1_000_000
    return round(cost, 8)


def record_llm_response(stage: str, model: str, response: Any) -> None:
    events = _usage_events.get()
    if events is None:
        return

    usage = getattr(response, "usage", None)
    if usage is None:
        return

    input_tokens = _get_usage_value(usage, "input_tokens", "prompt_tokens")
    output_tokens = _get_usage_value(usage, "output_tokens", "completion_tokens")
    total_tokens = _get_usage_value(usage, "total_tokens")
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    cached_tokens = _cached_input_tokens(usage)

    events.append(
        {
            "stage": stage,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_input_tokens": cached_tokens,
            "total_tokens": total_tokens,
            "estimated_cost": estimate_cost(model, input_tokens, output_tokens, cached_tokens),
        }
    )


def usage_summary() -> dict[str, Any]:
    events = current_usage_events()
    total_cost = sum(event["estimated_cost"] or 0 for event in events)
    return {
        "calls": events,
        "model_name": ",".join(dict.fromkeys(event["model"] for event in events)) or None,
        "prompt_tokens": sum(event["input_tokens"] for event in events),
        "completion_tokens": sum(event["output_tokens"] for event in events),
        "total_tokens": sum(event["total_tokens"] for event in events),
        "estimated_cost": round(total_cost, 8),
    }
