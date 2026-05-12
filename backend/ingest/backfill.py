from ingest.fetchers import get_boxscore_for_game, get_games_for_date
from ingest.normalizers import (
    normalize_game,
    normalize_player,
    normalize_team,
    normalize_player_game_stats,
    normalize_team_game_stats,
)
from ingest.writers import (
    upsert_player,
    upsert_game,
    upsert_team,
    insert_player_game_stats,
    insert_team_game_stats,
)
from app.schema import ensure_tables_if_enabled
from app.db import SessionLocal
from datetime import datetime, timedelta
import time
import pprint
import json
import random


# -----------------------------
# Retry / pacing configuration
# -----------------------------
GAME_FETCH_MAX_RETRIES = 4
DATE_FETCH_MAX_RETRIES = 4

GAME_FETCH_BASE_SLEEP = 4
DATE_FETCH_BASE_SLEEP = 8

PER_GAME_SUCCESS_SLEEP = 3
PER_DATE_SUCCESS_SLEEP = 8

GAME_FAILURE_EXTRA_SLEEP = 10
DATE_FAILURE_COOLDOWN = 120

CONSECUTIVE_BAD_DATE_THRESHOLD = 3
MAX_REWINDS_PER_START_DATE = 3


def sleep_with_jitter(seconds: float) -> None:
    jitter = random.uniform(0, 1.5)
    time.sleep(seconds + jitter)


def fetch_with_retries(fetch_fn, *args, max_retries: int, base_sleep: float, **kwargs):
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return fetch_fn(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if attempt == max_retries:
                raise

            backoff = base_sleep * (2 ** attempt)
            sleep_with_jitter(backoff)

    raise last_exception


def ingest_single_game(game_id: str) -> dict:
    session = SessionLocal()

    try:
        boxscore = fetch_with_retries(
            get_boxscore_for_game,
            game_id=game_id,
            max_retries=GAME_FETCH_MAX_RETRIES,
            base_sleep=GAME_FETCH_BASE_SLEEP,
        )

        game_context = boxscore["game"]
        player_boxscores = boxscore["player"]
        team_boxscores = boxscore["team"]

        # First normalize team stats to get point differentials
        all_normalized_team_game_stats = []
        point_differential_by_team = {}
        
        for team_boxscore in team_boxscores:
            normalized_team = normalize_team(team_boxscore)
            upsert_team(session=session, team_dict=normalized_team)

            normalized_team_stats = normalize_team_game_stats(team_boxscore, game_context=game_context)
            all_normalized_team_game_stats.append(normalized_team_stats)
            
            # Store point differential for player stats
            point_differential_by_team[team_boxscore['team_id']] = team_boxscore['diff']

        # Add point_differential to game_context for player normalization
        game_context['point_differential'] = point_differential_by_team

        # Normalize game with team_stats to extract scores
        normalized_game = normalize_game(game_context, team_stats=team_boxscores)

        with session as session:
            upsert_game(session=session, game_dict=normalized_game)

            all_normalized_player_game_stats = []
            for player_boxscore in player_boxscores:
                normalized_player = normalize_player(player_boxscore)
                upsert_player(session=session, player_dict=normalized_player)

                all_normalized_player_game_stats.append(
                    normalize_player_game_stats(player_boxscore, game_context=game_context)
                )

            insert_team_game_stats(session=session, rows=all_normalized_team_game_stats)
            insert_player_game_stats(session=session, rows=all_normalized_player_game_stats)

            session.commit()

        sleep_with_jitter(PER_GAME_SUCCESS_SLEEP)

        return {
            "game_id": game_id,
            "status": "success",
            "players_processed": len(player_boxscores),
            "teams_processed": len(team_boxscores),
        }

    except Exception as e:
        session.rollback()
        sleep_with_jitter(GAME_FAILURE_EXTRA_SLEEP)

        return {
            "game_id": game_id,
            "status": "failed",
            "error": str(e),
        }

    finally:
        session.close()


def ingest_date(game_date: str) -> dict:
    try:
        games = fetch_with_retries(
            get_games_for_date,
            game_date=game_date,
            max_retries=DATE_FETCH_MAX_RETRIES,
            base_sleep=DATE_FETCH_BASE_SLEEP,
        )
    except Exception as e:
        return {
            "game_date": game_date,
            "status": "failed",
            "games_found": 0,
            "games_succeeded": 0,
            "games_failed": 0,
            "games_processed": [],
            "results": {},
            "error": f"failed to fetch games for date: {str(e)}",
        }

    games_processed_out = {}
    games_succeeded = 0
    games_failed = 0

    for game in games:
        game_id = game["game_id"]

        try:
            game_ingestion_output = ingest_single_game(game_id=game_id)
            games_processed_out[game_id] = game_ingestion_output

            if game_ingestion_output["status"] == "success":
                games_succeeded += 1
            else:
                games_failed += 1

        except Exception as e:
            games_processed_out[game_id] = {
                "game_id": game_id,
                "status": "failed",
                "error": str(e),
            }
            games_failed += 1
            sleep_with_jitter(GAME_FAILURE_EXTRA_SLEEP)

    return {
        "game_date": game_date,
        "status": "success" if games_failed == 0 else "partial_success",
        "games_found": len(games),
        "games_succeeded": games_succeeded,
        "games_failed": games_failed,
        "games_processed": list(games_processed_out.keys()),
        "results": games_processed_out,
    }


def backfill_range(start_date: str, end_date: str) -> dict:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    backfill_out = {
        "start_date": start_date,
        "end_date": end_date,
        "dates_processed": 0,
        "games_found": 0,
        "games_succeeded": 0,
        "games_failed": 0,
        "daily_results": [],
    }

    consecutive_bad_dates = 0
    bad_streak_start_date = None
    rewind_attempts_by_start_date = {}

    with open('logs.txt', 'w') as f:
        pass

    current = start
    while current <= end:
        current_date_str = current.strftime("%Y-%m-%d")
        out = ingest_date(current_date_str)

        backfill_out["dates_processed"] += 1
        backfill_out["games_found"] += out["games_found"]
        backfill_out["games_succeeded"] += out["games_succeeded"]
        backfill_out["games_failed"] += out["games_failed"]
        backfill_out["daily_results"].append(out)

        print(f'Processed {out["games_succeeded"]}/{out["games_found"]} on {current_date_str}')

        with open("logs.txt", "a") as f:
            json.dump(out, f)
            f.write("\n")

        is_bad_date = out["status"] in {"failed", "partial_success"}

        if is_bad_date:
            consecutive_bad_dates += 1
            if bad_streak_start_date is None:
                bad_streak_start_date = current_date_str
        else:
            consecutive_bad_dates = 0
            bad_streak_start_date = None

        if consecutive_bad_dates >= CONSECUTIVE_BAD_DATE_THRESHOLD:
            rewind_key = bad_streak_start_date
            rewind_attempts = rewind_attempts_by_start_date.get(rewind_key, 0)

            if rewind_attempts < MAX_REWINDS_PER_START_DATE:
                rewind_attempts_by_start_date[rewind_key] = rewind_attempts + 1

                print(
                    f"Hit {consecutive_bad_dates} consecutive bad dates starting at "
                    f"{bad_streak_start_date}. Cooling down for {DATE_FAILURE_COOLDOWN} "
                    f"seconds, then rewinding to {bad_streak_start_date} "
                    f"(attempt {rewind_attempts + 1}/{MAX_REWINDS_PER_START_DATE})."
                )

                sleep_with_jitter(DATE_FAILURE_COOLDOWN)

                current = datetime.strptime(bad_streak_start_date, "%Y-%m-%d")
                consecutive_bad_dates = 0
                bad_streak_start_date = None
                continue
            else:
                print(
                    f"Max rewinds reached for bad streak starting at {bad_streak_start_date}. "
                    f"Skipping rewind and continuing forward."
                )
                consecutive_bad_dates = 0
                bad_streak_start_date = None
                sleep_with_jitter(PER_DATE_SUCCESS_SLEEP)
        else:
            sleep_with_jitter(PER_DATE_SUCCESS_SLEEP)

        current += timedelta(days=1)

    return backfill_out


if __name__ == "__main__":
    ensure_tables_if_enabled()

    # Run initial backfill
    print("=" * 80)
    print("STARTING INITIAL BACKFILL")
    print("=" * 80)
    
    result = backfill_range(start_date="2026-05-08", end_date="2026-05-11")
    
    # Collect dates that failed or partially succeeded
    failed_or_partial_dates = []
    for daily_result in result["daily_results"]:
        if daily_result["status"] in ["failed", "partial_success"]:
            failed_or_partial_dates.append(daily_result["game_date"])
    
    print("\n" + "=" * 80)
    print(f"INITIAL BACKFILL COMPLETE")
    print(f"Total dates processed: {result['dates_processed']}")
    print(f"Total games found: {result['games_found']}")
    print(f"Total games succeeded: {result['games_succeeded']}")
    print(f"Total games failed: {result['games_failed']}")
    print(f"Dates needing retry: {len(failed_or_partial_dates)}")
    print("=" * 80)
    
    # Retry failed/partial dates after waiting
    if failed_or_partial_dates:
        print(f"\nFound {len(failed_or_partial_dates)} dates to retry:")
        print(failed_or_partial_dates)
        print("\nWaiting 10 minutes before retrying...")
        sleep_with_jitter(600)  # 10 minutes
        
        print("\n" + "=" * 80)
        print("STARTING RETRY OF FAILED/PARTIAL DATES")
        print("=" * 80)
        
        retry_results = []
        for date in failed_or_partial_dates:
            print(f"\nRetrying {date}...")
            retry_result = ingest_date(date)
            retry_results.append(retry_result)
            pprint.pprint(retry_result)
        
        # Summary of retry
        retry_succeeded = sum(1 for r in retry_results if r["status"] == "success")
        retry_still_failed = len(retry_results) - retry_succeeded
        
        print("\n" + "=" * 80)
        print("RETRY COMPLETE")
        print(f"Dates retried: {len(retry_results)}")
        print(f"Now successful: {retry_succeeded}")
        print(f"Still failed/partial: {retry_still_failed}")
        print("=" * 80)
        
        # Show any dates that still failed
        if retry_still_failed > 0:
            still_problematic = [r["game_date"] for r in retry_results if r["status"] != "success"]
            print(f"\nDates still needing attention: {still_problematic}")
    else:
        print("\n✅ All dates processed successfully on first pass!")
