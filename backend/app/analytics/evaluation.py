from __future__ import annotations

import json
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from openai import OpenAI

from app.config import ANALYTICS_AUTO_REVIEW_MODEL, ANALYTICS_CLAIM_EXTRACTION_MODEL, OPENAI_API_KEY
from app.models.analytics import ChatQueryEvent


logger = logging.getLogger(__name__)


NUMERIC_FIELD_RE = re.compile(
    r"(?P<value>-?\d+(?:\.\d+)?)\s*(?P<label>points?|pts|rebounds?|reb|assists?|ast|turnovers?|tov|steals?|blocks?|games?)",
    re.IGNORECASE,
)

METRIC_ALIASES = {
    "point": "pts",
    "points": "pts",
    "pts": "pts",
    "rebound": "reb",
    "rebounds": "reb",
    "reb": "reb",
    "assist": "ast",
    "assists": "ast",
    "ast": "ast",
    "turnover": "tov",
    "turnovers": "tov",
    "tov": "tov",
    "steals": "stl",
    "blocks": "blk",
    "games": "game_count",
}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None


def _round_expected(value: Any) -> float | None:
    numeric = _to_float(value)
    if numeric is None:
        return None
    return round(numeric, 1)


def expected_values_from_rows(event: ChatQueryEvent) -> list[dict[str, Any]]:
    payload = event.analytics_payload or {}
    execution = payload.get("execution_result") or {}
    rows = execution.get("final_output") or []
    if not isinstance(rows, list) or len(rows) != 1:
        return []

    row = rows[0]
    expected = []
    for key, value in row.items():
        if not isinstance(value, (int, float, str)):
            continue
        numeric = _round_expected(value)
        if numeric is None:
            continue
        metric = key
        if key.endswith("_mean"):
            metric = key.replace("_mean", "")
        expected.append(
            {
                "metric": metric,
                "source_field": key,
                "value": numeric,
                "tolerance": 0.11,
            }
        )
    return expected


def regex_extract_claims(response: str | None) -> list[dict[str, Any]]:
    if not response:
        return []
    claims = []
    for match in NUMERIC_FIELD_RE.finditer(response):
        label = match.group("label").lower()
        metric = METRIC_ALIASES.get(label.rstrip("s"), METRIC_ALIASES.get(label))
        value = _to_float(match.group("value"))
        if metric and value is not None:
            claims.append({"metric": metric, "value": value, "unit": "unknown", "method": "regex"})
    return claims


def llm_extract_claims(event: ChatQueryEvent) -> list[dict[str, Any]]:
    if not OPENAI_API_KEY or not event.bot_response:
        return []

    expected_metrics = sorted({item["metric"] for item in expected_values_from_rows(event)})
    if not expected_metrics:
        return []

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=ANALYTICS_CLAIM_EXTRACTION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract objective numeric/statistical claims from the assistant answer. "
                        "Return only JSON with a top-level claims array. Do not judge correctness. "
                        "Use metric names from the allowed list when possible."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": event.user_message,
                            "answer": event.bot_response,
                            "allowed_metrics": expected_metrics,
                        }
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        claims = parsed.get("claims") or []
        if isinstance(claims, list):
            return [claim for claim in claims if isinstance(claim, dict)]
    except Exception:
        logger.exception("LLM claim extraction failed for analytics event %s", event.id)
    return []


def extract_claims(event: ChatQueryEvent, *, allow_llm: bool = True) -> list[dict[str, Any]]:
    claims = regex_extract_claims(event.bot_response)
    if claims:
        return claims
    if not allow_llm:
        return []
    return llm_extract_claims(event)


def compare_claims(expected: list[dict[str, Any]], extracted: list[dict[str, Any]]) -> tuple[bool | None, list[dict[str, Any]]]:
    if not expected:
        return None, []
    if not extracted:
        return None, []

    mismatches = []
    matched = 0
    for expected_item in expected:
        metric = expected_item["metric"]
        expected_value = expected_item["value"]
        tolerance = expected_item.get("tolerance", 0.11)
        candidates = [claim for claim in extracted if claim.get("metric") == metric]
        if not candidates:
            continue
        matched += 1
        actual_value = _to_float(candidates[0].get("value"))
        if actual_value is None or abs(actual_value - expected_value) > tolerance:
            mismatches.append(
                {
                    "metric": metric,
                    "expected": expected_value,
                    "actual": actual_value,
                    "tolerance": tolerance,
                }
            )

    if matched == 0:
        return None, []
    return len(mismatches) == 0, mismatches


def llm_review_answer(event: ChatQueryEvent) -> dict[str, Any]:
    if event.error_type or not event.bot_response:
        return {
            "classification": "incorrect",
            "confidence": "high",
            "rationale": "The chatbot did not produce a usable answer for this question.",
            "requires_user_decision": False,
        }

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    current_date = date.today().isoformat()
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=ANALYTICS_AUTO_REVIEW_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are doing a presentation sanity check for an NBA chatbot answer. "
                    f"Today's date is {current_date}. Use this date for interpreting relative date phrases "
                    "like today, yesterday, this season, current, latest, and last game. "
                    "Pretend all NBA stats in the answer are true by default. Do not fact-check whether "
                    "the stats are historically accurate or credible. "
                    "Classify only as correct or ambiguous. "
                    "Use correct when the answer directly addresses the question and would be acceptable "
                    "if the stated stats were guaranteed to be true. "
                    "Use ambiguous when a human should decide, including partial answers, unclear questions, "
                    "missing context, self-contradictions, or stats that fail an obvious basketball sanity check. "
                    "Only sanity-check stats for extreme impossibilities or wildly implausible claims, such as "
                    "Steph Curry averaged 200 points per game or Draymond Green had 29 blocks in one game. "
                    "Do not mark normal-looking stat values ambiguous just because they might need verification. "
                    "Do not return incorrect unless there was no answer, an execution error, or an obvious non-answer; "
                    "those cases are handled before this LLM call. "
                    "Return only JSON with exactly these keys: classification, confidence, rationale. "
                    "The rationale must be one or two concise sentences explaining the sanity-check decision, "
                    "without claiming that the underlying NBA stats are true or false."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": event.user_message,
                        "answer": event.bot_response,
                        "chatbot_status": event.chatbot_status,
                        "error_type": event.error_type,
                    }
                ),
            },
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    parsed = json.loads(content)
    classification = str(parsed.get("classification", "ambiguous")).strip().lower()
    if classification == "incorrect":
        classification = "ambiguous"
    if classification not in {"correct", "ambiguous"}:
        classification = "ambiguous"

    rationale = (
        parsed.get("rationale")
        or parsed.get("reason")
        or parsed.get("explanation")
        or parsed.get("justification")
    )
    if not rationale:
        rationale = (
            "The answer appears coherent and responsive, but the reviewer should make the final call."
            if classification == "correct"
            else "The answer needs human review because the sanity check could not confidently mark it correct."
        )

    return {
        "classification": classification,
        "confidence": parsed.get("confidence") or "unknown",
        "rationale": str(rationale),
        "requires_user_decision": classification == "ambiguous",
    }
