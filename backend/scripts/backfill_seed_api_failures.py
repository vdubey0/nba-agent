#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.analytics.capture import record_chat_event


FAILED_API_QUESTIONS = [
    "What shooting percentages did the Warriors allow in the 2025-26 regular season?",
    "Which Warriors players averaged the most points, rebounds, and assists in the 2025-26 regular season?",
    "How many turnovers did the Warriors force over their last 10 regular season games in 2025-26?",
]


def main() -> int:
    failures = 0
    for index, question in enumerate(FAILED_API_QUESTIONS, 1):
        event_id = record_chat_event(
            source="seed_api_query",
            user_message=question,
            result={
                "status": "error",
                "response": None,
                "error": {
                    "message": "Seed API request returned HTTP 500.",
                    "details": "Backfilled from seed script terminal log.",
                },
            },
            latency_ms=None,
            http_status=500,
            analytics_payload={
                "outcome_hint": "error",
                "error": {
                    "message": "Seed API request returned HTTP 500.",
                    "details": "Backfilled from seed script terminal log.",
                },
            },
            benchmark_run_id="seed-backfill-terminal-log",
            benchmark_case_id=f"seed_api_backfill_{index:03d}",
        )
        if event_id:
            print(f"backfilled {event_id}: {question}")
        else:
            failures += 1
            print(f"failed to backfill: {question}")

    print(f"done: {len(FAILED_API_QUESTIONS) - failures} inserted, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
