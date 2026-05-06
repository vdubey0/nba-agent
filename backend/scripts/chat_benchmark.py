#!/usr/bin/env python3
"""Benchmark /api/chat with answerable NBA analytics questions.

The goal is to collect resume-useful metrics:
- endpoint success rate
- plan/execution sanity rate
- latency distribution
- lightweight response-shape correctness checks

This script intentionally uses only the Python standard library so it can run
inside the existing backend venv without adding dependencies.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://localhost:8000"


BENCHMARK_CASES: list[dict[str, Any]] = [
    {
        "id": "player_recent_games",
        "family": "player game log",
        "question": "What were Steph Curry's last 5 regular season games in 2025-26?",
        "must_contain_any": ["curry", "steph", "points", "pts"],
        "expected_scopes": ["player_game_stats"],
        "min_rows": 1,
    },
    {
        "id": "player_season_averages",
        "family": "player aggregation",
        "question": "What were Steph Curry's average points, rebounds, assists, and turnovers in the 2025-26 regular season?",
        "must_contain_any": ["points", "rebounds", "assists", "turnovers", "curry"],
        "expected_scopes": ["player_game_stats"],
        "required_aggregation_fields": ["pts", "reb", "ast", "tov"],
        "min_rows": 1,
    },
    {
        "id": "player_opponent_split",
        "family": "opponent split",
        "question": "How did Steph Curry perform against each opponent in the 2025-26 regular season?",
        "must_contain_any": ["opponent", "points", "assists", "curry"],
        "expected_scopes": ["player_game_stats"],
        "min_rows": 1,
    },
    {
        "id": "player_shooting_metrics",
        "family": "advanced player metric",
        "question": "What were Steph Curry's true shooting percentage, effective field goal percentage, field goal percentage, three-point percentage, and free throw percentage in the 2025-26 regular season?",
        "must_contain_any": ["true shooting", "effective", "field goal", "three-point", "free throw"],
        "expected_scopes": ["player_game_stats"],
        "required_derived_metrics": ["ts_pct", "efg_pct", "fg_pct", "fg3_pct", "ft_pct"],
        "min_rows": 1,
    },
    {
        "id": "team_recent_games",
        "family": "team game log",
        "question": "What were the Warriors' last 5 regular season team games in 2025-26?",
        "must_contain_any": ["warriors", "points", "regular season"],
        "expected_scopes": ["team_game_stats"],
        "check_score_consistency": True,
        "min_rows": 1,
    },
    {
        "id": "team_season_averages",
        "family": "team aggregation",
        "question": "What were the Warriors' average points for, points allowed, rebounds, assists, and turnovers in the 2025-26 regular season?",
        "must_contain_any": ["warriors", "points", "rebounds", "assists", "turnovers"],
        "expected_scopes": ["team_game_stats"],
        "required_aggregation_fields": ["pf", "pa", "reb", "ast", "tov"],
        "min_rows": 1,
    },
    {
        "id": "team_allowed_stats",
        "family": "opponent perspective",
        "question": "How many points, rebounds, assists, and turnovers did the Warriors allow on average in the 2025-26 regular season?",
        "must_contain_any": ["allowed", "points", "rebounds", "assists", "turnovers"],
        "expected_scopes": ["team_game_stats"],
        "expected_perspectives": ["opponent"],
        "required_aggregation_fields": ["pf", "reb", "ast", "tov"],
        "min_rows": 1,
    },
    {
        "id": "team_leaderboard_scoring",
        "family": "league leaderboard",
        "question": "Which teams scored the most points per game in the 2025-26 regular season?",
        "must_contain_any": ["points", "per game", "teams"],
        "expected_scopes": ["team_game_stats"],
        "required_aggregation_fields": ["pf"],
        "min_rows": 1,
    },
    {
        "id": "team_leaderboard_turnovers_forced",
        "family": "league defensive leaderboard",
        "question": "Which teams forced the most turnovers in the 2025-26 regular season?",
        "must_contain_any": ["turnovers", "forced", "teams"],
        "expected_scopes": ["team_game_stats"],
        "expected_perspectives": ["opponent"],
        "required_aggregation_fields": ["tov"],
        "min_rows": 1,
    },
    {
        "id": "team_shooting_allowed",
        "family": "advanced team metric",
        "question": "What shooting percentages did the Warriors allow in the 2025-26 regular season?",
        "must_contain_any": ["warriors", "shooting", "field goal", "three-point"],
        "expected_scopes": ["team_game_stats"],
        "expected_perspectives": ["opponent"],
        "required_derived_metrics": ["efg_pct", "fg_pct", "fg3_pct", "ft_pct"],
        "min_rows": 1,
    },
    {
        "id": "team_player_leaderboard",
        "family": "team player leaderboard",
        "question": "Which Warriors players averaged the most points, rebounds, and assists in the 2025-26 regular season?",
        "must_contain_any": ["warriors", "players", "points", "rebounds", "assists"],
        "expected_scopes": ["player_game_stats"],
        "required_aggregation_fields": ["pts", "reb", "ast"],
        "min_rows": 1,
    },
    {
        "id": "last_n_defensive_stat",
        "family": "last-N aggregation",
        "question": "How many turnovers did the Warriors force over their last 10 regular season games in 2025-26?",
        "must_contain_any": ["turnovers", "warriors", "last 10"],
        "expected_scopes": ["team_game_stats"],
        "expected_perspectives": ["opponent"],
        "required_aggregation_fields": ["tov"],
        "min_rows": 1,
    },
]


@dataclass
class CaseResult:
    id: str
    family: str
    question: str
    passed: bool
    status: str
    latency_ms: float
    http_status: int | None
    checks: dict[str, bool]
    issues: list[str]
    response: str | None
    plan_type: str | None
    step_count: int
    result_row_count: int | None
    final_rows_preview: list[dict[str, Any]] | None
    raw_error: str | None = None


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return response.status, json.loads(body)


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = round((len(ordered) - 1) * pct)
    return ordered[rank]


def get_final_rows(payload: dict[str, Any]) -> tuple[str | None, int, list[dict[str, Any]] | None]:
    steps = (payload.get("intermediate_steps") or {})
    plan = steps.get("plan") or {}
    plan_steps = plan.get("steps") or []
    if not plan_steps:
        return None, 0, None

    final_step_id = plan_steps[-1].get("step_id")
    execution = steps.get("execution_result") or {}
    rows = execution.get(final_step_id)
    if not isinstance(rows, list):
        return final_step_id, len(plan_steps), None
    return final_step_id, len(plan_steps), rows


def collect_query_specs(plan: dict[str, Any]) -> list[dict[str, Any]]:
    specs = []
    for step in plan.get("steps") or []:
        if step.get("step_type") == "query":
            query_spec = (step.get("payload") or {}).get("query_spec")
            if isinstance(query_spec, dict):
                specs.append(query_spec)
    return specs


def all_expected_scopes_present(case: dict[str, Any], query_specs: list[dict[str, Any]]) -> bool:
    expected = case.get("expected_scopes")
    if not expected:
        return True
    scopes = {spec.get("scope") for spec in query_specs}
    return bool(scopes) and scopes.issubset(set(expected))


def expected_perspective_present(case: dict[str, Any], query_specs: list[dict[str, Any]]) -> bool:
    expected = case.get("expected_perspectives")
    if not expected:
        return True
    perspectives = {spec.get("perspective", "self") for spec in query_specs}
    return bool(perspectives.intersection(expected))


def required_aggregation_fields_present(case: dict[str, Any], query_specs: list[dict[str, Any]]) -> bool:
    required = set(case.get("required_aggregation_fields") or [])
    if not required:
        return True
    present: set[str] = set()
    for spec in query_specs:
        aggregations = spec.get("aggregations") or {}
        if isinstance(aggregations, dict):
            present.update(aggregations.keys())
    return required.issubset(present)


def required_derived_metrics_present(case: dict[str, Any], query_specs: list[dict[str, Any]]) -> bool:
    required = set(case.get("required_derived_metrics") or [])
    if not required:
        return True
    present: set[str] = set()
    for spec in query_specs:
        derived_metrics = spec.get("derived_metrics") or []
        if isinstance(derived_metrics, list):
            present.update(derived_metrics)
    return required.issubset(present)


def score_rows_are_consistent(case: dict[str, Any], final_rows: list[dict[str, Any]] | None) -> bool:
    if not case.get("check_score_consistency"):
        return True
    if not final_rows:
        return False

    for row in final_rows:
        pf = row.get("pf")
        pa = row.get("pa")
        diff = row.get("point_differential")
        is_win = row.get("is_win")
        if pf is None or pa is None or diff is None:
            return False
        if pf - pa != diff:
            return False
        if is_win is True and pf <= pa:
            return False
        if is_win is False and pf >= pa:
            return False
    return True


def evaluate_case(case: dict[str, Any], payload: dict[str, Any], latency_ms: float, http_status: int) -> CaseResult:
    response = payload.get("response")
    response_text = response or ""
    response_lower = response_text.lower()
    status = payload.get("status", "missing")

    steps = payload.get("intermediate_steps") or {}
    plan = steps.get("plan") or {}
    entities = steps.get("entities") or []
    final_step_id, step_count, final_rows = get_final_rows(payload)
    query_specs = collect_query_specs(plan)

    checks: dict[str, bool] = {
        "http_200": http_status == 200,
        "status_success": status == "success",
        "nonempty_response": bool(response_text.strip()),
        "has_intermediate_steps": bool(steps),
        "has_plan": bool(plan.get("steps")),
        "has_final_rows": isinstance(final_rows, list) and len(final_rows) >= case.get("min_rows", 1),
        "no_ambiguous_entities": not any(entity.get("status") == "ambiguous" for entity in entities),
        "contains_expected_language": any(term in response_lower for term in case.get("must_contain_any", [])),
        "no_obvious_error_language": not any(term in response_lower for term in ["failed", "could not", "sorry", "error"]),
        "expected_query_scope": all_expected_scopes_present(case, query_specs),
        "expected_perspective": expected_perspective_present(case, query_specs),
        "required_aggregation_fields": required_aggregation_fields_present(case, query_specs),
        "required_derived_metrics": required_derived_metrics_present(case, query_specs),
        "score_rows_consistent": score_rows_are_consistent(case, final_rows),
    }

    issues = [name for name, ok in checks.items() if not ok]
    passed = not issues

    preview = None
    if isinstance(final_rows, list):
        preview = final_rows[:3]

    result_row_count = len(final_rows) if isinstance(final_rows, list) else None

    return CaseResult(
        id=case["id"],
        family=case["family"],
        question=case["question"],
        passed=passed,
        status=status,
        latency_ms=latency_ms,
        http_status=http_status,
        checks=checks,
        issues=issues,
        response=response,
        plan_type=plan.get("plan_type"),
        step_count=step_count,
        result_row_count=result_row_count,
        final_rows_preview=preview,
    )


def run_case(base_url: str, case: dict[str, Any], timeout: float, benchmark_run_id: str | None = None) -> CaseResult:
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "conversation_id": None,
        "message": case["question"],
        "include_steps": True,
        "source": "benchmark",
        "benchmark_run_id": benchmark_run_id,
        "benchmark_case_id": case["id"],
    }

    started = time.perf_counter()
    try:
        http_status, response_payload = post_json(url, payload, timeout=timeout)
        latency_ms = (time.perf_counter() - started) * 1000
        return evaluate_case(case, response_payload, latency_ms, http_status)
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        try:
            raw = exc.read().decode("utf-8")
        except Exception:
            raw = str(exc)
        return CaseResult(
            id=case["id"],
            family=case["family"],
            question=case["question"],
            passed=False,
            status="http_error",
            latency_ms=latency_ms,
            http_status=exc.code,
            checks={},
            issues=["http_error"],
            response=None,
            plan_type=None,
            step_count=0,
            result_row_count=None,
            final_rows_preview=None,
            raw_error=raw,
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return CaseResult(
            id=case["id"],
            family=case["family"],
            question=case["question"],
            passed=False,
            status="request_error",
            latency_ms=latency_ms,
            http_status=None,
            checks={},
            issues=["request_error"],
            response=None,
            plan_type=None,
            step_count=0,
            result_row_count=None,
            final_rows_preview=None,
            raw_error=repr(exc),
        )


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    latencies = [result.latency_ms for result in results if result.http_status == 200]
    passed = sum(1 for result in results if result.passed)
    success = sum(1 for result in results if result.status == "success")
    plan_ok = sum(1 for result in results if result.checks.get("has_plan"))
    final_rows_ok = sum(1 for result in results if result.checks.get("has_final_rows"))

    return {
        "case_count": len(results),
        "passed_count": passed,
        "passed_rate": round(passed / len(results), 4) if results else 0,
        "endpoint_success_count": success,
        "endpoint_success_rate": round(success / len(results), 4) if results else 0,
        "plan_present_count": plan_ok,
        "plan_present_rate": round(plan_ok / len(results), 4) if results else 0,
        "final_rows_present_count": final_rows_ok,
        "final_rows_present_rate": round(final_rows_ok / len(results), 4) if results else 0,
        "latency_ms": {
            "median": round(statistics.median(latencies), 2) if latencies else None,
            "p95": round(percentile(latencies, 0.95), 2) if latencies else None,
            "min": round(min(latencies), 2) if latencies else None,
            "max": round(max(latencies), 2) if latencies else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the NBA agent /api/chat endpoint.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-dir", default="benchmark_reports")
    args = parser.parse_args()

    cases = BENCHMARK_CASES[: args.limit] if args.limit else BENCHMARK_CASES
    results: list[CaseResult] = []
    benchmark_run_id = str(uuid.uuid4())

    print(f"Running {len(cases)} /api/chat benchmark cases against {args.base_url}")
    for index, case in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] {case['id']}: {case['question']}")
        result = run_case(args.base_url, case, timeout=args.timeout, benchmark_run_id=benchmark_run_id)
        results.append(result)
        verdict = "PASS" if result.passed else "FAIL"
        issues = f" issues={','.join(result.issues)}" if result.issues else ""
        print(
            f"  {verdict} status={result.status} latency={result.latency_ms:.0f}ms "
            f"plan={result.plan_type} rows={result.result_row_count}{issues}"
        )

    summary = summarize(results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_run_id": benchmark_run_id,
        "base_url": args.base_url,
        "summary": summary,
        "results": [asdict(result) for result in results],
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"chat_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nSummary")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote report: {output_path}")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
