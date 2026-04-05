from app.query.query_spec import validate_query_spec, run_query_spec
from app.orchestrator.planning import validate_plan, plan_question
from app.db import SessionLocal
import pprint
from openai import OpenAI
from app.orchestrator.entity_extraction import resolve_entity_mentions, extract_entity_mentions

def execute_extract_ids_step(step_payload: dict, step_outputs: dict) -> dict:
    try:
        source_step_id = step_payload['source_step_id']
        source_field = step_payload['source_field']

        prev_output = step_outputs[source_step_id]

        if not isinstance(prev_output, list):
            return {
                'status': 'failed',
                'error_message': f"Output from step {source_step_id} is not a list"
            }

        out = []
        for row in prev_output:
            if source_field in row and row[source_field] not in out:
                out.append(row[source_field])

        return {
            'status': 'success',
            'data': out
        }

    except KeyError as e:
        return {
            'status': 'failed',
            'error_message': f"Missing key in extract_ids step: {e}"
        }


def execute_filter_rows_step(step_payload: dict, step_outputs: dict) -> dict:
    try:
        source_step_id = step_payload['source_step_id']
        filter_ids_step_id = step_payload['filter_ids_step_id']
        source_field = step_payload['source_field']

        prev_output = step_outputs[source_step_id]
        filter_ids = step_outputs[filter_ids_step_id]

        if not isinstance(prev_output, list):
            return {
                'status': 'failed',
                'error_message': f"Output from step {source_step_id} is not a list"
            }

        if not isinstance(filter_ids, list):
            return {
                'status': 'failed',
                'error_message': f"Output from step {filter_ids_step_id} is not a list"
            }

        out = []
        for row in prev_output:
            if row.get(source_field) in filter_ids:
                out.append(row)

        return {
            'status': 'success',
            'data': out
        }

    except KeyError as e:
        return {
            'status': 'failed',
            'error_message': f"Missing key in filter_rows step: {e}"
        }


def execute_query_step(session, step: dict):
    query_spec = step['payload']['query_spec']
    validate_out = validate_query_spec(query_spec=query_spec)

    if validate_out['status'] == 'failed':
        return {
            'status': 'failed',
            'error_message': f"Step {step['step_id']} Query Spec Validation Error: {validate_out['message']}"
        }

    query_out = run_query_spec(session=session, query_spec=query_spec)

    if query_out['status'] == 'failed':
        return {
            'status': 'failed',
            'error_message': f"Step {step['step_id']} Run Query Error: {query_out['message']}"
        }

    return {
        'status': 'success',
        'data': query_out['rows']
    }

def execute_plan(session, plan: dict) -> dict:
    validate_out = validate_plan(plan=plan)
    if validate_out['status'] == 'failed':
        return {
            'status': 'failed',
            'message': f"Validate plan failed with errors: {validate_out['errors']}"
        }

    step_outputs = {}
    steps = plan['steps']
    final_out = None

    for i, step in enumerate(steps):
        step_out = None

        if step['step_type'] == 'query':
            step_out = execute_query_step(session=session, step=step)

        elif step['step_type'] == 'extract_ids':
            step_out = execute_extract_ids_step(
                step_payload=step['payload'],
                step_outputs=step_outputs
            )

        elif step['step_type'] == 'filter_rows':
            step_out = execute_filter_rows_step(
                step_payload=step['payload'],
                step_outputs=step_outputs
            )

        else:
            return {
                'status': 'failed',
                'message': f"Unsupported step type: {step['step_type']}"
            }

        if step_out['status'] == 'failed':
            return {
                'status': 'failed',
                'message': step_out['error_message'],
                'step_outputs': step_outputs
            }

        step_outputs[step['step_id']] = step_out['data']

        if i == len(steps) - 1:
            final_out = step_out['data']

    return {
        'status': 'success',
        'final_output': final_out,
        'step_outputs': step_outputs
    }

if __name__ == "__main__":
    question = "How many points does Steph Curry score against the top 10 teams who force the most turnovers?"
    session = SessionLocal()
    client = OpenAI()

    mentions = extract_entity_mentions(client=client, question=question)
    entities = resolve_entity_mentions(session=session, mentions=mentions)
    plan = plan_question(client=client, question=question, resolved_entities=entities)
    out = execute_plan(session=session, plan=plan)

    pprint.pprint(out['final_output'])