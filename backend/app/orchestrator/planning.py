from openai import OpenAI
import json
import pprint
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from app.orchestrator.entity_extraction import extract_entity_mentions, resolve_entity_mentions
from app.db import SessionLocal
from app.utils.retry import retry_with_context, format_retry_context_for_prompt

load_dotenv()

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "planning-prompt.txt"
PLANNING_PROMPT = PROMPT_PATH.read_text()


@retry_with_context(max_attempts=3)
def plan_question(
    client,
    question: str,
    resolved_entities: list[dict],
    retry_context: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Create a query plan with retry logic.
    
    Args:
        client: OpenAI client
        question: User's question
        resolved_entities: List of resolved entities
        retry_context: Injected by retry decorator on retry attempts
    
    Returns:
        Query plan dict or error dict
    """
    prompt = PLANNING_PROMPT
    
    # Add retry context if this is a retry attempt
    if retry_context:
        prompt += format_retry_context_for_prompt(retry_context)

    planner_input = {
        "question": question,
        "resolved_entities": resolved_entities
    }

    response = client.responses.create(
        model="gpt-5.4",
        input=[
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": json.dumps(planner_input, indent=2)
            }
        ],
        temperature=0.0
    )

    output_text = response.output[0].content[0].text.strip()
    try:
        plan = json.loads(output_text)
    except json.JSONDecodeError as e:
        return {
            'status': 'failed',
            'error': f'JSON parsing failed:\nError: {e.msg}\nLine {e.lineno}, Column: {e.colno}',
            'raw_text': output_text
        }
    
    # Validate the plan before returning
    validation_result = validate_plan(plan)
    if validation_result['status'] == 'failed':
        return {
            'status': 'failed',
            'error': f"Plan validation failed: {', '.join(validation_result['errors'])}",
            'raw_text': output_text
        }
    
    return plan

VALID_PLAN_TYPES = {
    "single_query",
    "multi_leaderboard",
    "derived_cohort",
    "multi_query"
}

VALID_STEP_TYPES = {
    "query",
    "extract_ids",
    "filter_rows"
}

def validate_plan(plan: dict):
    errors = []

    if 'plan_type' not in plan:
        errors.append("'plan_type' must exist in plan")
    elif plan['plan_type'] not in VALID_PLAN_TYPES:
        errors.append(f"Invalid plan_type '{plan['plan_type']}'")

    if 'steps' not in plan:
        errors.append("'steps' must exist in plan")
        return {"status": "failed", "errors": errors}

    if not isinstance(plan['steps'], list):
        errors.append("'steps' must be of type list")
        return {"status": "failed", "errors": errors}

    if len(plan['steps']) == 0:
        errors.append("'steps' cannot be empty")
        return {"status": "failed", "errors": errors}

    # -----------------------
    # 3. Step validation
    # -----------------------
    seen_step_ids = set()

    for i, step in enumerate(plan['steps'], 1):
        prefix = f"Step {i}"

        if not isinstance(step, dict):
            errors.append(f"{prefix} must be a dict")
            continue

        # step_id
        if 'step_id' not in step:
            errors.append(f"{prefix} missing 'step_id'")
        else:
            if step['step_id'] in seen_step_ids:
                errors.append(f"{prefix} duplicate step_id '{step['step_id']}'")
            seen_step_ids.add(step['step_id'])

        # step_type
        if 'step_type' not in step:
            errors.append(f"{prefix} missing 'step_type'")
            continue
        elif step['step_type'] not in VALID_STEP_TYPES:
            errors.append(f"{prefix} invalid step_type '{step['step_type']}'")
            continue

        step_type = step['step_type']

        # -----------------------
        # query step
        # -----------------------
        if step_type == "query":
            if 'query_spec' not in step['payload']:
                errors.append(f"{prefix} query step must have 'query_spec'")
            elif not isinstance(step['payload']['query_spec'], dict):
                errors.append(f"{prefix} query_spec must be a dict")

        # -----------------------
        # extract_ids step
        # -----------------------
        elif step_type == "extract_ids":
            if 'source_step_id' not in step['payload']:
                errors.append(f"{prefix} extract_ids must have 'source_step_id'")
            if 'source_field' not in step['payload']:
                errors.append(f"{prefix} extract_ids must have 'source_field'")

        # -----------------------
        # filter_rows step
        # -----------------------
        elif step_type == "filter_rows":
            if 'source_step_id' not in step['payload']:
                errors.append(f"{prefix} filter_rows must have 'souce_step_id'")
            if 'source_field' not in step['payload']:
                errors.append(f"{prefix} filter_rows must have 'source_field'")
            if 'filter_ids_step_id' not in step['payload']:
                errors.append(f"{prefix} filter_rows must have 'filter_ids_step_id'")

    # -----------------------
    # 4. Plan-type specific rules
    # -----------------------
    plan_type = plan.get('plan_type')

    if plan_type == "single_query":
        if len(plan['steps']) != 1:
            errors.append("single_query must have exactly 1 step")
        elif plan['steps'][0].get('step_type') != "query":
            errors.append("single_query step must be of type 'query'")

    elif plan_type == "multi_leaderboard":
        for step in plan['steps']:
            if step.get('step_type') != "query":
                errors.append("multi_leaderboard can only contain query steps")

    elif plan_type == "derived_cohort":
        step_types = [s.get('step_type') for s in plan['steps']]

        if "extract_ids" not in step_types:
            errors.append("derived_cohort must include an extract_ids step")

        if "filter_rows" not in step_types:
            errors.append("derived_cohort must include a filter_rows step")

        query_steps = [s for s in plan['steps'] if s.get('step_type') == "query"]
        if len(query_steps) < 2:
            errors.append("derived_cohort must have at least 2 query steps")

    elif plan_type == "multi_query":
        query_steps = [s for s in plan['steps'] if s.get('step_type') == "query"]
        if len(query_steps) < 2:
            errors.append("multi_query must have at least 2 query steps")

    # -----------------------
    # 5. Final return
    # -----------------------
    if len(errors) > 0:
        return {
            "status": "failed",
            "errors": errors
        }

    return {
        "status": "success"
    }

    


if __name__ == '__main__':
    client = OpenAI()
    session = SessionLocal()

    representative_questions = [
        ("What were Steph Curry's last 5 regular season games in 2025-26?", "single_query"),
        ("Which Warriors players averaged the most points, rebounds, and assists in the 2025-26 regular season?", "multi_leaderboard"),
        ("Which teams forced the most turnovers in the 2025-26 regular season?", "single_query"),
        ("What were Steph Curry's true shooting, effective field goal percentage, field goal percentage, three-point percentage, and free throw percentage in the 2025-26 regular season?", "single_query"),
        ("Which opponent teams' players averaged the most points and turnovers against the Warriors in the 2025-26 regular season?", "multi_leaderboard"),
        ("How many points does Steph Curry score against the top 10 teams who force the most turnovers?", "derived_cohort")
    ]


    for i, question_info in enumerate(representative_questions, 1):
        question, question_type = question_info

        mentions = extract_entity_mentions(client=client, question=question)
        entities = resolve_entity_mentions(session=session, mentions=mentions)
        
        print(f"{i}. {question}")

        pprint.pprint(plan_question(client, question=question, resolved_entities=entities))
        print('\n')
