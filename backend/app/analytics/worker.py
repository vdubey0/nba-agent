from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from app.analytics.processor import process_event
from app.config import (
    ANALYTICS_PROCESSING_TIMEOUT_SECONDS,
    ANALYTICS_WORKER_BATCH_SIZE,
    ANALYTICS_WORKER_SLEEP_SECONDS,
)
from app.db import SessionLocal
from app.models.analytics import AnalyticsJob, ChatQueryEvent


logger = logging.getLogger(__name__)


def process_pending_jobs(limit: int = ANALYTICS_WORKER_BATCH_SIZE) -> int:
    session = SessionLocal()
    processed = 0
    stale_before = datetime.utcnow() - timedelta(seconds=ANALYTICS_PROCESSING_TIMEOUT_SECONDS)

    try:
        jobs = (
            session.query(AnalyticsJob)
            .filter(
                (AnalyticsJob.status.in_(["pending", "retrying"]))
                | (
                    (AnalyticsJob.status == "processing")
                    & (AnalyticsJob.started_at.isnot(None))
                    & (AnalyticsJob.started_at < stale_before)
                )
            )
            .order_by(AnalyticsJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
            .all()
        )

        for job in jobs:
            job.status = "processing"
            job.started_at = datetime.utcnow()
            job.completed_at = None
            job.attempt_count += 1
            session.commit()

            try:
                event = session.query(ChatQueryEvent).filter(ChatQueryEvent.id == job.query_event_id).one()
                process_event(session, event, allow_llm_claim_extraction=False)
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.last_error = None
                session.commit()
                processed += 1
            except Exception as exc:
                session.rollback()
                job = session.query(AnalyticsJob).filter(AnalyticsJob.id == job.id).one()
                job.status = "retrying" if job.attempt_count < 3 else "failed"
                job.last_error = repr(exc)
                job.completed_at = datetime.utcnow() if job.status == "failed" else None
                session.commit()
                logger.exception("Failed analytics job %s", job.id)
    finally:
        session.close()

    return processed


async def run_analytics_worker_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            processed = await asyncio.to_thread(process_pending_jobs)
            if processed:
                logger.info("Processed %s analytics job(s)", processed)
        except Exception:
            logger.exception("Analytics background worker failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=ANALYTICS_WORKER_SLEEP_SECONDS)
        except asyncio.TimeoutError:
            pass
