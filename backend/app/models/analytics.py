from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ChatQueryEvent(Base):
    __tablename__ = "chat_query_events"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, nullable=True, index=True)
    source = Column(String, nullable=False, default="unknown", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=True)
    chatbot_status = Column(String, nullable=True, index=True)
    http_status = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)

    model_name = Column(String, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)

    plan_type = Column(String, nullable=True, index=True)
    step_count = Column(Integer, nullable=True)
    result_row_count = Column(Integer, nullable=True)

    intermediate_steps = Column(JSONB, nullable=True)
    analytics_payload = Column(JSONB, nullable=True)
    error_type = Column(String, nullable=True, index=True)
    error_message = Column(Text, nullable=True)

    benchmark_run_id = Column(String, nullable=True, index=True)
    benchmark_case_id = Column(String, nullable=True, index=True)

    jobs = relationship("AnalyticsJob", back_populates="event", cascade="all, delete-orphan")
    evaluation = relationship("ChatEvaluation", back_populates="event", uselist=False, cascade="all, delete-orphan")
    question_analysis = relationship(
        "ChatQuestionAnalysis",
        back_populates="event",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AnalyticsJob(Base):
    __tablename__ = "analytics_jobs"

    id = Column(String, primary_key=True, default=_uuid)
    query_event_id = Column(String, ForeignKey("chat_query_events.id"), nullable=False, index=True)
    job_type = Column(String, nullable=False, default="process_chat_event", index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    event = relationship("ChatQueryEvent", back_populates="jobs")


class ChatEvaluation(Base):
    __tablename__ = "chat_evaluations"

    id = Column(String, primary_key=True, default=_uuid)
    query_event_id = Column(String, ForeignKey("chat_query_events.id"), nullable=False, unique=True, index=True)
    evaluation_status = Column(String, nullable=False, default="pending", index=True)
    outcome = Column(String, nullable=False, default="answered", index=True)
    is_error = Column(Boolean, nullable=False, default=False)
    is_verifiable = Column(Boolean, nullable=False, default=False)
    is_correct = Column(Boolean, nullable=True)
    expected_values = Column(JSONB, nullable=True)
    extracted_values = Column(JSONB, nullable=True)
    mismatches = Column(JSONB, nullable=True)
    evaluation_method = Column(String, nullable=True)
    tolerance = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    event = relationship("ChatQueryEvent", back_populates="evaluation")


class ChatQuestionAnalysis(Base):
    __tablename__ = "chat_question_analysis"

    id = Column(String, primary_key=True, default=_uuid)
    query_event_id = Column(String, ForeignKey("chat_query_events.id"), nullable=False, unique=True, index=True)
    intent_category = Column(String, nullable=True, index=True)
    entities = Column(JSONB, nullable=True)
    players = Column(JSONB, nullable=True)
    teams = Column(JSONB, nullable=True)
    stats = Column(JSONB, nullable=True)
    time_range = Column(JSONB, nullable=True)
    complexity_type = Column(String, nullable=True, index=True)
    embedding = Column(JSONB, nullable=True)
    cluster_id = Column(String, ForeignKey("question_clusters.id"), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    event = relationship("ChatQueryEvent", back_populates="question_analysis")
    cluster = relationship("QuestionCluster", back_populates="analyses")


class QuestionCluster(Base):
    __tablename__ = "question_clusters"

    id = Column(String, primary_key=True, default=_uuid)
    label = Column(String, nullable=True)
    representative_question = Column(Text, nullable=False)
    query_count = Column(Integer, nullable=False, default=1)
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    metadata_json = Column(JSONB, nullable=True)

    analyses = relationship("ChatQuestionAnalysis", back_populates="cluster")


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id = Column(String, primary_key=True, default=_uuid)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    base_url = Column(String, nullable=True)
    summary = Column(JSONB, nullable=True)


class BenchmarkCaseResult(Base):
    __tablename__ = "benchmark_case_results"

    id = Column(String, primary_key=True, default=_uuid)
    benchmark_run_id = Column(String, ForeignKey("benchmark_runs.id"), nullable=False, index=True)
    query_event_id = Column(String, ForeignKey("chat_query_events.id"), nullable=True, index=True)
    case_id = Column(String, nullable=False, index=True)
    family = Column(String, nullable=True, index=True)
    question = Column(Text, nullable=False)
    passed = Column(Boolean, nullable=False, default=False)
    objective_outcome = Column(String, nullable=True, index=True)
    latency_ms = Column(Float, nullable=True)
    checks = Column(JSONB, nullable=True)
    issues = Column(JSONB, nullable=True)
    response = Column(Text, nullable=True)
    final_rows_preview = Column(JSONB, nullable=True)
