import logging
import os
import sys
from datetime import UTC, datetime, timedelta

from app.db import engine
from app.schema import ensure_tables_if_enabled
from ingest.backfill import ingest_date


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %s", name, raw_value, default)
        return default

    if value < 1:
        logger.warning("Invalid %s=%r; using default %s", name, raw_value, default)
        return default

    return value


def run_daily_update() -> int:
    today = datetime.now(UTC).date()
    lag_days = _parse_positive_int("DAILY_UPDATE_LAG_DAYS", 1)
    lookback_days = _parse_positive_int("DAILY_UPDATE_LOOKBACK_DAYS", 2)
    target_dates = [
        today - timedelta(days=days_ago)
        for days_ago in range(lag_days, lag_days + lookback_days)
    ]

    total_games_found = 0
    total_games_succeeded = 0
    total_games_failed = 0
    failed_dates: list[str] = []

    for target_date in target_dates:
        game_date = target_date.isoformat()
        logger.info("Starting ingest for %s", game_date)

        result = ingest_date(game_date)
        total_games_found += result.get("games_found", 0)
        total_games_succeeded += result.get("games_succeeded", 0)
        total_games_failed += result.get("games_failed", 0)

        status = result.get("status")
        if status == "success":
            logger.info(
                "Finished ingest for %s (%s/%s games succeeded)",
                game_date,
                result.get("games_succeeded", 0),
                result.get("games_found", 0),
            )
            continue

        failed_dates.append(game_date)

        if status == "partial_success":
            logger.warning(
                "Date ingest partially succeeded for %s (%s/%s games succeeded)",
                game_date,
                result.get("games_succeeded", 0),
                result.get("games_found", 0),
            )
        else:
            logger.error("Date ingest failed for %s: %s", game_date, result.get("error"))

    logger.info(
        "Daily update summary: games_found=%s games_succeeded=%s games_failed=%s failed_dates=%s",
        total_games_found,
        total_games_succeeded,
        total_games_failed,
        failed_dates,
    )

    return 1 if failed_dates else 0


def main() -> int:
    logger.info("Daily update job started at %s", datetime.now(UTC).isoformat())

    try:
        ensure_tables_if_enabled()
        exit_code = run_daily_update()
        logger.info("Daily update job finished with exit code %s", exit_code)
        return exit_code
    except Exception:
        logger.exception("Daily update job failed")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
