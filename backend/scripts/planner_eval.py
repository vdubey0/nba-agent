from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.orchestrator.entity_extraction import extract_entity_mentions, resolve_entity_mentions
from app.orchestrator.llm_usage import start_usage_tracking, usage_summary
from app.orchestrator.planning import plan_question, validate_plan


CASES_PATH = ROOT / "app" / "orchestrator" / "planner_eval_cases.json"


def _query_specs(plan: dict[str, Any]) -> list[dict[str, Any]]:
    specs = []
    for step in plan.get("steps") or []:
        spec = (step.get("payload") or {}).get("query_spec")
        if isinstance(spec, dict):
            specs.append(spec)
    return specs


def _check_plan(plan: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    issues = []

    expected_plan_type = expected.get("plan_type")
    if expected_plan_type and plan.get("plan_type") != expected_plan_type:
        issues.append(f"expected plan_type {expected_plan_type}, got {plan.get('plan_type')}")

    steps = plan.get("steps") or []
    min_steps = expected.get("min_steps")
    max_steps = expected.get("max_steps")
    if min_steps is not None and len(steps) < min_steps:
        issues.append(f"expected at least {min_steps} steps, got {len(steps)}")
    if max_steps is not None and len(steps) > max_steps:
        issues.append(f"expected at most {max_steps} steps, got {len(steps)}")

    step_types = {step.get("step_type") for step in steps}
    for step_type in expected.get("required_step_types") or []:
        if step_type not in step_types:
            issues.append(f"missing required step_type {step_type}")

    derived_metrics = {
        metric
        for spec in _query_specs(plan)
        for metric in (spec.get("derived_metrics") or [])
        if isinstance(metric, str)
    }
    for metric in expected.get("required_derived_metrics") or []:
        if metric not in derived_metrics:
            issues.append(f"missing required derived metric {metric}")

    validation = validate_plan(plan)
    if validation.get("status") == "failed":
        issues.append(f"plan validation failed: {validation.get('errors')}")

    return issues


def run_case(client: OpenAI, case: dict[str, Any]) -> dict[str, Any]:
    session = SessionLocal()
    start_usage_tracking()
    try:
        mentions = extract_entity_mentions(client=client, question=case["question"])
        if isinstance(mentions, dict) and mentions.get("status") == "failed":
            return {"id": case["id"], "passed": False, "issues": [mentions.get("error")], "usage": usage_summary()}

        entities = resolve_entity_mentions(session=session, mentions=mentions)
        entity_failures = [entity for entity in entities if entity.get("status") in {"failed", "not_found"}]
        if entity_failures:
            return {"id": case["id"], "passed": False, "issues": [f"entity resolution failed: {entity_failures}"], "usage": usage_summary()}

        plan = plan_question(client=client, question=case["question"], resolved_entities=entities)
        if isinstance(plan, dict) and plan.get("status") == "failed":
            return {"id": case["id"], "passed": False, "issues": [plan.get("error")], "usage": usage_summary()}

        issues = _check_plan(plan, case.get("expected") or {})
        return {
            "id": case["id"],
            "family": case.get("family"),
            "passed": not issues,
            "issues": issues,
            "plan_type": plan.get("plan_type"),
            "step_count": len(plan.get("steps") or []),
            "usage": usage_summary(),
        }
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run planner regression evals against golden capability cases.")
    parser.add_argument("--cases", default=str(CASES_PATH), help="Path to planner eval cases JSON.")
    parser.add_argument("--family", help="Only run cases from this family.")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text())
    if args.family:
        cases = [case for case in cases if case.get("family") == args.family]

    client = OpenAI()
    results = [run_case(client, case) for case in cases]
    passed = sum(1 for result in results if result["passed"])

    print(json.dumps({"passed": passed, "total": len(results), "results": results}, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
