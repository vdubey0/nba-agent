from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.analytics.classification import (
    assign_cluster,
    classify_complexity,
    classify_intent,
    extract_entities,
    extract_stats,
    extract_time_range,
    simple_embedding,
)
from app.analytics.evaluation import compare_claims, expected_values_from_rows, extract_claims
from app.analytics.outcome import deterministic_outcome
from app.models.analytics import ChatEvaluation, ChatQueryEvent, ChatQuestionAnalysis


logger = logging.getLogger(__name__)
MANUAL_REVIEW_METHODS = {"manual_review", "llm_assisted_manual_review"}


def process_event(session: Session, event: ChatQueryEvent, *, allow_llm_claim_extraction: bool = True) -> None:
    outcome, error_type = deterministic_outcome(event)
    if error_type and not event.error_type:
        event.error_type = error_type

    evaluation = (
        session.query(ChatEvaluation)
        .filter(ChatEvaluation.query_event_id == event.id)
        .one_or_none()
    )
    preserve_manual_review = evaluation and evaluation.evaluation_method in MANUAL_REVIEW_METHODS

    expected = []
    extracted = []
    mismatches = []
    is_correct = None
    is_verifiable = False
    evaluation_method = "deterministic_outcome"

    if not preserve_manual_review and outcome == "answered":
        expected = expected_values_from_rows(event)
        extracted = extract_claims(event, allow_llm=allow_llm_claim_extraction)
        comparison, mismatches = compare_claims(expected, extracted)
        if comparison is None:
            outcome = "unverifiable"
            evaluation_method = "claim_extraction_unverifiable"
        else:
            if comparison:
                is_verifiable = True
                is_correct = True
                outcome = "correct"
                evaluation_method = "db_row_claim_comparison"
            else:
                outcome = "unverifiable"
                evaluation_method = "db_row_claim_mismatch_unverifiable"

    if not evaluation:
        evaluation = ChatEvaluation(query_event_id=event.id)
        session.add(evaluation)
    elif not preserve_manual_review:
        session.refresh(evaluation)
        preserve_manual_review = evaluation.evaluation_method in MANUAL_REVIEW_METHODS

    if not preserve_manual_review:
        evaluation.evaluation_status = "completed"
        evaluation.outcome = outcome
        evaluation.is_error = outcome == "error"
        evaluation.is_verifiable = is_verifiable
        evaluation.is_correct = is_correct
        evaluation.expected_values = expected
        evaluation.extracted_values = extracted
        evaluation.mismatches = mismatches
        evaluation.evaluation_method = evaluation_method
        evaluation.tolerance = {"default_numeric": 0.11}
        evaluation.created_at = datetime.utcnow()

    entities = extract_entities(event)
    embedding = simple_embedding(event.user_message)
    cluster_id = assign_cluster(session, event, embedding)

    analysis = (
        session.query(ChatQuestionAnalysis)
        .filter(ChatQuestionAnalysis.query_event_id == event.id)
        .one_or_none()
    )
    if not analysis:
        analysis = ChatQuestionAnalysis(query_event_id=event.id)
        session.add(analysis)

    analysis.intent_category = classify_intent(event)
    analysis.entities = entities["raw"]
    analysis.players = entities["players"]
    analysis.teams = entities["teams"]
    analysis.stats = extract_stats(event)
    analysis.time_range = extract_time_range(event)
    analysis.complexity_type = classify_complexity(event)
    analysis.embedding = embedding
    analysis.cluster_id = cluster_id
    analysis.created_at = datetime.utcnow()
