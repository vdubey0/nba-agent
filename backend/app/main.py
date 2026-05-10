import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import text

from app.analytics.routes import router as analytics_router
from app.analytics.worker import run_analytics_worker_loop
from app.chat_service import run_tracked_chat_message
from app.config import (
    ANALYTICS_BACKGROUND_WORKER_ENABLED,
    APP_ENV,
    APP_VERSION,
    AUTO_CREATE_TABLES,
    CORS_ORIGINS,
    OPENAI_API_KEY,
)
from app.db import SessionLocal, engine
from app.orchestrator.entity_extraction import extract_entity_mentions, resolve_entity_mentions
from app.schema import ensure_tables_if_enabled


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if AUTO_CREATE_TABLES:
        ensure_tables_if_enabled()
    else:
        logger.info("AUTO_CREATE_TABLES disabled, skipping automatic schema creation")

    analytics_stop_event: asyncio.Event | None = None
    analytics_worker_task: asyncio.Task | None = None
    if ANALYTICS_BACKGROUND_WORKER_ENABLED:
        analytics_stop_event = asyncio.Event()
        analytics_worker_task = asyncio.create_task(run_analytics_worker_loop(analytics_stop_event))
        logger.info("Analytics background worker started")

    try:
        yield
    finally:
        if analytics_stop_event and analytics_worker_task:
            analytics_stop_event.set()
            try:
                await asyncio.wait_for(analytics_worker_task, timeout=5)
            except asyncio.TimeoutError:
                analytics_worker_task.cancel()
                try:
                    await analytics_worker_task
                except asyncio.CancelledError:
                    pass
            logger.info("Analytics background worker stopped")


app = FastAPI(lifespan=lifespan)
app.include_router(analytics_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=OPENAI_API_KEY)


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    include_steps: bool = False
    source: Optional[str] = None
    benchmark_run_id: Optional[str] = None
    benchmark_case_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: Optional[str] = None
    status: str
    response: Optional[str] = None
    clarification: Optional[dict] = None
    intermediate_steps: Optional[dict] = None
    error: Optional[dict] = None


class QueryRequest(BaseModel):
    message: str
    include_steps: bool = False
    source: Optional[str] = None
    benchmark_run_id: Optional[str] = None
    benchmark_case_id: Optional[str] = None


class ResolveEntitiesRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ResolveEntitiesResponse(BaseModel):
    status: str
    resolved_entities: Optional[list[dict[str, Any]]] = None
    conversation_id: Optional[str] = None
    error: Optional[dict[str, Any]] = None


class QueryResponse(BaseModel):
    status: str
    response: Optional[str] = None
    clarification: Optional[dict] = None
    intermediate_steps: Optional[dict] = None
    error: Optional[dict] = None
    resolved_entities: Optional[list[dict[str, Any]]] = None
    plan: Optional[dict[str, Any]] = None
    execution_metadata: Optional[dict[str, Any]] = None


@app.get("/health")
def health_check():
    return {"status": "ok", "environment": APP_ENV, "version": APP_VERSION}


@app.get("/db-check")
def db_check():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        value = result.scalar()
    return {"db_connected": value == 1}


@app.get("/tables")
def list_tables():
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
        )
        tables = [row[0] for row in result]
    return {"tables": tables}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = run_tracked_chat_message(
            client=client,
            message=request.message,
            conversation_id=request.conversation_id,
            include_steps=request.include_steps,
            source=request.source or "api_chat",
            http_status=200,
            benchmark_run_id=request.benchmark_run_id,
            benchmark_case_id=request.benchmark_case_id,
        )
        return ChatResponse(**result)
    except Exception as exc:
        logger.exception("Unexpected top-level failure in /api/chat")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    logger.info("Received /api/query request for question: %s", request.message)
    try:
        result = run_tracked_chat_message(
            client=client,
            message=request.message,
            conversation_id=None,
            include_steps=request.include_steps,
            source=request.source or "api_query",
            http_status=200,
            benchmark_run_id=request.benchmark_run_id,
            benchmark_case_id=request.benchmark_case_id,
        )
        return QueryResponse(**result)
    except Exception as exc:
        logger.exception("Unexpected top-level failure in /api/query")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/resolve-entities", response_model=ResolveEntitiesResponse)
async def resolve_entities(request: ResolveEntitiesRequest):
    logger.info("Received /api/resolve-entities request for question: %s", request.message)
    session = SessionLocal()
    conversation = None

    if request.conversation_id:
        from app.models.conversation import conversation_store

        conversation = conversation_store.get_conversation(request.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        mentions = extract_entity_mentions(
            client=client,
            question=request.message,
            conversation=conversation,
        )

        if isinstance(mentions, dict) and mentions.get("status") == "failed":
            return ResolveEntitiesResponse(
                status="error",
                conversation_id=request.conversation_id,
                error={
                    "message": "Failed to extract entities.",
                    "details": mentions,
                },
            )

        entities = resolve_entity_mentions(
            session=session,
            mentions=mentions,
            conversation=conversation,
        )

        return ResolveEntitiesResponse(
            status="success",
            resolved_entities=entities,
            conversation_id=request.conversation_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected top-level failure in /api/resolve-entities")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    from app.models.conversation import conversation_store

    try:
        conversation = conversation_store.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch conversation")
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    from app.models.conversation import conversation_store

    try:
        success = conversation_store.delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "deleted", "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete conversation")
        raise HTTPException(status_code=500, detail=str(exc))
