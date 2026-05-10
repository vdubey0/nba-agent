#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.analytics.worker import process_pending_jobs
from app.config import ANALYTICS_WORKER_BATCH_SIZE, ANALYTICS_WORKER_SLEEP_SECONDS
from app.schema import ensure_tables_if_enabled


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


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
