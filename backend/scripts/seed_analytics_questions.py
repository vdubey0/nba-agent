#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openai import OpenAI

from app.analytics.capture import record_chat_event
from app.chat_service import run_tracked_query
from app.schema import ensure_tables_if_enabled


BENCHMARK_QUESTIONS = [
    "What were Steph Curry's last 5 regular season games in 2025-26?",
    "What were Steph Curry's average points, rebounds, assists, and turnovers in the 2025-26 regular season?",
    "How did Steph Curry perform against each opponent in the 2025-26 regular season?",
    "What were Steph Curry's true shooting percentage, effective field goal percentage, field goal percentage, three-point percentage, and free throw percentage in the 2025-26 regular season?",
    "What were the Warriors' last 5 regular season team games in 2025-26?",
    "What were the Warriors' average points for, points allowed, rebounds, assists, and turnovers in the 2025-26 regular season?",
    "How many points, rebounds, assists, and turnovers did the Warriors allow on average in the 2025-26 regular season?",
    "Which teams scored the most points per game in the 2025-26 regular season?",
    "Which teams forced the most turnovers in the 2025-26 regular season?",
    "What shooting percentages did the Warriors allow in the 2025-26 regular season?",
    "Which Warriors players averaged the most points, rebounds, and assists in the 2025-26 regular season?",
    "How many turnovers did the Warriors force over their last 10 regular season games in 2025-26?",
]


CAPABILITY_QUESTIONS = [
    "How did LeBron James perform in Lakers wins this season?",
    "What did the Celtics average in close games?",
    "How did the Knicks perform in blowout wins?",
    "How many threes did LeBron make against the Cavs?",
    "What was Nikola Jokic's highest assist game this season?",
    "What was Jayson Tatum's standard deviation in points in the regular season?",
    "Show Kevin Durant's games with at least 30 points.",
    "What were Luka Doncic's stats over his last 10 games?",
    "Show Anthony Edwards' last 3 games against the Nuggets.",
    "What were Steph Curry's averages against the Spurs in the 2025-26 regular season?",
    "Which opponents did Steph Curry score the most total points against?",
    "Against which opponents did Steph Curry have the highest true shooting percentage?",
    "How many rebounds did the Lakers average at home?",
    "What was the Nuggets' record in close games?",
    "How many turnovers and steals did the Warriors force on average?",
    "Which teams allowed the fewest points per game?",
    "Which teams allowed the lowest effective field goal percentage?",
    "Which players had the highest scoring averages in the 2025-26 regular season?",
    "Which opposing players averaged the most points against the Warriors?",
    "Which players had the lowest standard deviation in points with a minimum of 40 games played?",
    "Which teams averaged the most rebounds, offensive rebounds, and defensive rebounds?",
    "Which teams allowed the fewest rebounds per game?",
    "Which teams had the best offensive shooting percentages?",
    "Who scores, rebounds, and assists the most against the Warriors?",
    "Top teams in points, rebounds, and assists this season.",
    "Which Warriors players lead the team in points, assists, and rebounds?",
    "Compare Steph Curry and LeBron James this season.",
    "Compare Warriors vs Lakers stats in the 2025-26 regular season.",
    "How does Jalen Brunson perform in wins vs losses?",
    "How do the Warriors perform with Steph Curry versus without Steph Curry?",
    "What is the Warriors' record this season?",
    "What is the Warriors' record this season without Steph Curry?",
    "What is the Celtics' record in close games?",
    "What is the Lakers' home record in the regular season?",
    "How do the Grizzlies perform when Ja Morant plays?",
    "How does Anthony Davis average when LeBron James does not play?",
    "Compare the Lakers' points per game with LeBron versus without LeBron.",
    "Show Steph Curry's 30+ point games this season.",
    "How did Giannis Antetokounmpo perform in games with at least 10 rebounds?",
    "What did the Nuggets average in games where they had 30 or more assists?",
    "Among players who average at least 15 points per game, which players had the lowest standard deviation in points?",
    "Among players whose season high was at least 40 points, who had the lowest standard deviation in points?",
    "Which players with at least 60 games had the highest three-point percentage?",
    "Which players scored their season high vs the Warriors this season?",
    "Which players had their best rebounding game against the Lakers?",
    "How does Steph Curry play against the 10 teams that force the most turnovers?",
    "How do the Warriors perform against the top 5 defenses?",
    "How does Luka Doncic perform against the teams that allow the fewest points?",
    "Who scored the most points in the last Lakers game?",
    "Who had the most rebounds in the Warriors' last game?",
    "Who led the last Knicks game in assists?",
    "What was Steph Curry's game score average this season?",
    "Which players had the highest assist-to-turnover ratio?",
    "What was Brandon Ingram's fantasy score in wins?",
    "Which players had the highest points + rebounds + assists?",
    "What was the Warriors' net rating in the regular season?",
    "Which teams had the best offensive rating?",
    "What was the Celtics' pace over their last 10 games?",
    "Which teams had the best team turnover percentage?",
]


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int | None, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except Exception:
            return exc.code, {"status": "http_error", "error": str(exc)}
    except Exception as exc:
        return None, {"status": "request_error", "error": repr(exc)}


def record_seed_failure(
    *,
    source: str,
    question: str,
    seed_run_id: str,
    case_id: str,
    error_message: str,
    http_status: int | None = None,
) -> None:
    record_chat_event(
        source=source,
        user_message=question,
        result={
            "status": "error",
            "response": None,
            "error": {
                "message": "Seed script failed to process this question.",
                "details": error_message,
            },
        },
        latency_ms=None,
        http_status=http_status,
        analytics_payload={
            "outcome_hint": "error",
            "error": {
                "message": "Seed script failed to process this question.",
                "details": error_message,
            },
        },
        benchmark_run_id=seed_run_id,
        benchmark_case_id=case_id,
    )


def unique_questions(limit: int) -> list[str]:
    questions = []
    seen = set()
    for question in BENCHMARK_QUESTIONS + CAPABILITY_QUESTIONS:
        if question not in seen:
            seen.add(question)
            questions.append(question)
        if len(questions) >= limit:
            break
    return questions


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the analytics dashboard with tracked chatbot questions.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--api-count", type=int, default=25)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--include-steps", action="store_true")
    args = parser.parse_args()

    ensure_tables_if_enabled()
    seed_run_id = f"seed-{uuid.uuid4()}"
    questions = unique_questions(args.count)
    api_questions = questions[: args.api_count]
    local_questions = questions[args.api_count :]
    client = OpenAI()

    print(f"Seeding {len(questions)} analytics questions")
    print(f"  API /api/query: {len(api_questions)}")
    print(f"  Local tracked query: {len(local_questions)}")
    print(f"  Seed run: {seed_run_id}")

    failures = 0
    for index, question in enumerate(api_questions, 1):
        payload = {
            "message": question,
            "include_steps": args.include_steps,
            "source": "seed_api_query",
            "benchmark_run_id": seed_run_id,
            "benchmark_case_id": f"seed_api_{index:03d}",
        }
        status, response = post_json(f"{args.base_url.rstrip('/')}/api/query", payload, args.timeout)
        ok = status == 200 and response.get("status") in {"success", "needs_clarification", "error"}
        if not ok:
            failures += 1
            record_seed_failure(
                source="seed_api_query",
                question=question,
                seed_run_id=seed_run_id,
                case_id=f"seed_api_{index:03d}",
                error_message=json.dumps(response),
                http_status=status,
            )
        print(f"[api {index:02d}/{len(api_questions):02d}] status={status} chatbot={response.get('status')} {question}")
        time.sleep(args.sleep)

    for index, question in enumerate(local_questions, 1):
        try:
            response = run_tracked_query(
                client=client,
                message=question,
                include_steps=args.include_steps,
                source="seed_local_query",
                benchmark_run_id=seed_run_id,
                benchmark_case_id=f"seed_local_{index:03d}",
            )
            print(f"[local {index:02d}/{len(local_questions):02d}] chatbot={response.get('status')} {question}")
        except Exception as exc:
            failures += 1
            record_seed_failure(
                source="seed_local_query",
                question=question,
                seed_run_id=seed_run_id,
                case_id=f"seed_local_{index:03d}",
                error_message=repr(exc),
            )
            print(f"[local {index:02d}/{len(local_questions):02d}] failed={exc!r} {question}")
        time.sleep(args.sleep)

    print(f"Done. failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
