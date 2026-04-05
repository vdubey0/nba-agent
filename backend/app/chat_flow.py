"""
Conversational chat flow with support for:
- Multi-turn conversations with context
- Ambiguous entity clarification
- Stateless question answering for machine clients
- Intermediate step tracking
"""

from typing import Any, Dict, Optional
import logging

from openai import OpenAI

from app.db import SessionLocal
from app.models.conversation import Conversation, ResolvedEntity, conversation_store
from app.orchestrator.agent import execute_plan
from app.orchestrator.entity_extraction import (
    extract_entity_mentions,
    resolve_entity_mentions,
)
from app.orchestrator.planning import plan_question, validate_plan
from app.orchestrator.synthesis import synthesize_output
from app.utils.clarification import (
    create_entity_clarification,
    format_clarification_for_display,
    parse_clarification_response,
)

logger = logging.getLogger(__name__)


def answer_question(
    client: OpenAI,
    session,
    message: str,
    include_steps: bool = False,
) -> Dict[str, Any]:
    """
    Stateless QA pipeline for one-shot machine queries.
    """
    return _run_answer_pipeline(
        client=client,
        session=session,
        message=message,
        include_steps=include_steps,
        conversation=None,
    )


def process_message(
    client: OpenAI,
    message: str,
    conversation_id: Optional[str] = None,
    include_steps: bool = False,
) -> Dict[str, Any]:
    """
    Conversation-aware wrapper around the core QA pipeline.
    """
    session = SessionLocal()
    conversation: Optional[Conversation] = None

    try:
        conversation = conversation_store.get_or_create_conversation(conversation_id)
        conversation.add_message(role="user", content=message)

        if conversation.pending_clarification:
            return _handle_clarification_response(
                client=client,
                session=session,
                conversation=conversation,
                message=message,
                include_steps=include_steps,
            )

        result = _run_answer_pipeline(
            client=client,
            session=session,
            message=message,
            include_steps=include_steps,
            conversation=conversation,
        )

        return {"conversation_id": conversation.conversation_id, **result}

    except Exception as exc:
        logger.exception("Unexpected error processing chat message")
        return {
            "conversation_id": conversation.conversation_id if conversation else None,
            "status": "error",
            "error": {
                "message": "An unexpected error occurred",
                "details": str(exc),
            },
        }
    finally:
        session.close()


def _run_answer_pipeline(
    client: OpenAI,
    session,
    message: str,
    include_steps: bool,
    conversation: Optional[Conversation],
) -> Dict[str, Any]:
    logger.info("Starting QA pipeline for question: %s", message)

    mentions = extract_entity_mentions(
        client=client,
        question=message,
        conversation=conversation,
    )

    if isinstance(mentions, dict) and mentions.get("status") == "failed":
        logger.error("Entity extraction failed")
        return _build_error_result(
            message_text=f"Failed to extract entities: {mentions.get('error')}",
            details=mentions.get("error"),
            retry_count=mentions.get("retry_count", 0),
            conversation=conversation,
        )

    logger.info("Resolving %s entity mentions", len(mentions))
    entities = resolve_entity_mentions(
        session=session,
        mentions=mentions,
        conversation=conversation,
    )

    failed_entities = [entity for entity in entities if entity.get("status") == "failed"]
    if failed_entities:
        logger.error("Entity resolution failed")
        return _build_error_result(
            message_text="Failed to resolve one or more entities.",
            details=failed_entities,
            conversation=conversation,
        )

    ambiguous_entities = [entity for entity in entities if entity.get("status") == "ambiguous"]
    if ambiguous_entities:
        logger.info("Ambiguous entity detected for question: %s", message)
        return _build_clarification_result(
            ambiguous_entity=ambiguous_entities[0],
            conversation=conversation,
        )

    unresolved = [entity for entity in entities if entity.get("status") == "not_found"]
    if unresolved:
        logger.info("Unresolved entities detected for question: %s", message)
        return _build_error_result(
            message_text=f"Could not find: {', '.join(entity['surface_text'] for entity in unresolved)}",
            details={"unresolved_entities": unresolved},
            conversation=conversation,
        )

    logger.info("Planning query")
    plan = plan_question(
        client=client,
        question=message,
        resolved_entities=entities,
    )

    if isinstance(plan, dict) and plan.get("status") == "failed":
        logger.error("Planning failed")
        return _build_error_result(
            message_text=f"Failed to create query plan: {plan.get('error')}",
            details=plan.get("error"),
            retry_count=plan.get("retry_count", 0),
            conversation=conversation,
        )

    validation = validate_plan(plan)
    if validation.get("status") == "failed":
        logger.error("Plan validation failed")
        return _build_error_result(
            message_text=f"Invalid query plan: {validation.get('errors')}",
            details=validation.get("errors"),
            conversation=conversation,
        )

    logger.info("Executing query plan")
    execution_result = execute_plan(session=session, plan=plan)
    if execution_result.get("status") == "failed":
        logger.error("Query execution failed")
        return _build_error_result(
            message_text=f"Query execution failed: {execution_result.get('message')}",
            details=execution_result.get("message"),
            conversation=conversation,
        )

    logger.info("Synthesizing answer")
    answer = synthesize_output(
        client=client,
        question=message,
        rows=execution_result["final_output"],
        step_outputs=execution_result.get("step_outputs"),
        plan=plan,
    )

    if isinstance(answer, dict) and answer.get("status") == "failed":
        logger.error("Synthesis failed")
        return _build_error_result(
            message_text=f"Failed to synthesize answer: {answer.get('error')}",
            details=answer.get("error"),
            retry_count=answer.get("retry_count", 0),
            conversation=conversation,
        )

    answer_text = answer.get("output", "No answer generated")
    intermediate_steps = None
    if include_steps:
        intermediate_steps = {
            "entities": entities,
            "plan": plan,
            "execution_result": execution_result.get("step_outputs", {}),
        }

    if conversation:
        conversation.add_message(
            role="assistant",
            content=answer_text,
            intermediate_steps=intermediate_steps,
        )

    return {
        "status": "success",
        "response": answer_text,
        "clarification": None,
        "intermediate_steps": intermediate_steps,
        "error": None,
        "resolved_entities": entities,
        "plan": plan,
        "execution_metadata": {
            "step_count": len(plan.get("steps", [])),
            "result_row_count": len(execution_result.get("final_output", [])),
        },
    }


def _build_clarification_result(
    ambiguous_entity: Dict[str, Any],
    conversation: Optional[Conversation],
) -> Dict[str, Any]:
    entity_type = ambiguous_entity["entity_type"]
    surface_text = ambiguous_entity["surface_text"]

    if entity_type == "player":
        candidates = ambiguous_entity.get("players", [])
    elif entity_type == "team":
        candidates = ambiguous_entity.get("candidates", [])
    else:
        candidates = []

    clarification = create_entity_clarification(
        entity_type=entity_type,
        surface_text=surface_text,
        candidates=candidates,
    )
    clarification_dict = clarification.to_dict()

    if conversation:
        conversation.set_pending_clarification(clarification)
        conversation.add_message(
            role="assistant",
            content=format_clarification_for_display(clarification),
            metadata={"clarification_id": clarification.clarification_id},
        )

    return {
        "status": "needs_clarification",
        "response": None,
        "clarification": clarification_dict,
        "intermediate_steps": None,
        "error": None,
    }


def _build_error_result(
    message_text: str,
    details: Any,
    conversation: Optional[Conversation],
    retry_count: Optional[int] = None,
) -> Dict[str, Any]:
    if conversation:
        conversation.add_message(role="assistant", content=message_text)

    error_payload: Dict[str, Any] = {"message": message_text}
    if details is not None:
        if isinstance(details, dict):
            error_payload.update(details)
        else:
            error_payload["details"] = details
    if retry_count is not None:
        error_payload["retry_count"] = retry_count

    return {
        "status": "error",
        "response": None,
        "clarification": None,
        "intermediate_steps": None,
        "error": error_payload,
    }


def _handle_clarification_response(
    client: OpenAI,
    session,
    conversation: Conversation,
    message: str,
    include_steps: bool,
) -> Dict[str, Any]:
    clarification = conversation.pending_clarification
    selected_option = parse_clarification_response(message, clarification)

    if not selected_option:
        error_msg = "Invalid selection. Please choose a number from the list or type the full name."
        conversation.add_message(role="assistant", content=error_msg)
        return {
            "conversation_id": conversation.conversation_id,
            "status": "needs_clarification",
            "response": None,
            "clarification": clarification.to_dict(),
            "intermediate_steps": None,
            "error": {"message": error_msg},
        }

    entity_type = selected_option["entity_type"]
    surface_text = clarification.context["surface_text"]

    if entity_type == "player":
        resolved_entity = ResolvedEntity(
            entity_type="player",
            surface_text=surface_text,
            resolved_id=selected_option["entity_id"],
            resolved_name=selected_option["full_name"],
        )
    else:
        resolved_entity = ResolvedEntity(
            entity_type="team",
            surface_text=surface_text,
            resolved_id=selected_option["entity_id"],
            resolved_name=selected_option["team"],
        )

    conversation.cache_resolved_entity(surface_text, resolved_entity)
    conversation.clear_pending_clarification()

    original_question = None
    for msg in reversed(conversation.messages[:-1]):
        if msg.role == "user":
            original_question = msg.content
            break

    if not original_question:
        error_msg = "Could not find original question to continue processing."
        conversation.add_message(role="assistant", content=error_msg)
        return {
            "conversation_id": conversation.conversation_id,
            "status": "error",
            "response": None,
            "clarification": None,
            "intermediate_steps": None,
            "error": {"message": error_msg},
        }

    logger.info("Continuing after clarification with resolved entity: %s", resolved_entity.resolved_name)
    result = _run_answer_pipeline(
        client=client,
        session=session,
        message=original_question,
        include_steps=include_steps,
        conversation=conversation,
    )

    return {"conversation_id": conversation.conversation_id, **result}
