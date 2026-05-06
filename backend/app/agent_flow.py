from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown

from app.chat_service import run_tracked_query


def print_markdown(md_text):
    console.print(Markdown(md_text))


if __name__ == "__main__":
    client = OpenAI()
    console = Console()

    question = input("Please enter your question: ")
    result = run_tracked_query(
        client=client,
        message=question,
        include_steps=False,
        source="agent_flow",
    )

    if result.get("status") == "success":
        print_markdown(result.get("response") or "")
    else:
        print(result.get("error") or result)
