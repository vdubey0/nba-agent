from app.orchestrator.synthesis import synthesize_output
from app.orchestrator.agent import execute_plan
from app.orchestrator.planning import validate_plan, plan_question
from app.orchestrator.entity_extraction import resolve_entity_mentions, extract_entity_mentions
from app.db import SessionLocal
from openai import OpenAI
import sys
import pprint
from rich.console import Console
from rich.markdown import Markdown

def print_markdown(md_text):
    console.print(Markdown(md_text))

if __name__ == "__main__":
    session = SessionLocal()
    client = OpenAI()
    console = Console()

    question = input("Please enter your question: ")

    mentions = extract_entity_mentions(client=client, question=question)
    if 'status' in mentions:
        print('Error in extract_entity_mentions:')
        pprint.pprint(mentions)
        sys.exit()

    entities = resolve_entity_mentions(session=session, mentions=mentions)
    plan = plan_question(client=client, question=question, resolved_entities=entities)
    if 'status' in plan:
        print('Error in plan_question:')
        pprint.pprint(mentions)
        sys.exit()

    out = execute_plan(session=session, plan=plan)
    answer = synthesize_output(
        client=client,
        question=question,
        rows=out['final_output'],
        step_outputs=out.get('step_outputs'),
        plan=plan
    )

    print_markdown(answer['output'])
