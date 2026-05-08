#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.analytics.processor import process_event
from app.config import ANALYTICS_WORKER_BATCH_SIZE, ANALYTICS_WORKER_SLEEP_SECONDS
from app.db import SessionLocal
from app.models.analytics import AnalyticsJob, ChatQueryEvent
from app.schema import ensure_tables_if_enabled


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def process_pending_jobs(limit: int) -> int:
    session = SessionLocal()
    processed = 0
    try:
        jobs = (
            session.query(AnalyticsJob)
            .filter(AnalyticsJob.status.in_(["pending", "retrying"]))
            .order_by(AnalyticsJob.created_at.asc())
            .limit(limit)
            .all()
        )
        for job in jobs:
            job.status = "processing"
            job.started_at = datetime.utcnow()
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Process queued chatbot analytics jobs.")
    parser.add_argument("--once", action="store_true", help="Process one batch and exit.")
    parser.add_argument("--batch-size", type=int, default=ANALYTICS_WORKER_BATCH_SIZE)
    parser.add_argument("--sleep", type=float, default=ANALYTICS_WORKER_SLEEP_SECONDS)
    args = parser.parse_args()

    ensure_tables_if_enabled()
    while True:
        processed = process_pending_jobs(args.batch_size)
        if processed:
            logger.info("Processed %s analytics job(s)", processed)
        if args.once:
            break
        time.sleep(args.sleep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
