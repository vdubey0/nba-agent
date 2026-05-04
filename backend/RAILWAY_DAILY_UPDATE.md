# Railway Daily Update

Use Railway's built-in cron jobs for the recurring NBA data ingest. The cron service should use the same Postgres database as the web API and run this command:

```bash
python -m ingest.daily_update
```

## Local Backfill Against Railway Postgres

In `backend/.env`, replace the local database URL with the Railway Postgres connection string:

```env
DATABASE_URL=postgresql://postgres:<RAILWAY_PASSWORD>@<RAILWAY_HOST>:<RAILWAY_PORT>/railway
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
AUTO_CREATE_TABLES=true
APP_ENV=development
APP_VERSION=local
```

Get the real value from Railway Postgres > Variables. Prefer the public `DATABASE_URL` or `DATABASE_PUBLIC_URL` when running `backfill.py` from your laptop. Keep using the private/internal URL only for services running inside Railway.

Then run:

```bash
cd backend
source .venv/bin/activate
python ingest/backfill.py
```

## Cron Service Setup

Create a separate Railway service for the scheduled job, pointing at this repo with root directory `/backend`.

Set the service's config-as-code file to:

```text
/backend/railway.daily-update.json
```

The included schedule is:

```text
0 12 * * *
```

Railway evaluates cron schedules in UTC, so this runs daily at 12:00 UTC. That is 5:00 AM Pacific during daylight time and 4:00 AM Pacific during standard time.

Set these variables on the cron service:

```env
DATABASE_URL=<your Railway Postgres internal DATABASE_URL>
AUTO_CREATE_TABLES=true
APP_ENV=production
APP_VERSION=railway-cron
DAILY_UPDATE_LAG_DAYS=1
DAILY_UPDATE_LOOKBACK_DAYS=2
```

`daily_update.py` ingests yesterday and the day before by default. The database writes are upserts, so reprocessing the prior day is safe and helps catch late box score updates.

When `AUTO_CREATE_TABLES=true`, both `ingest/backfill.py` and `ingest/daily_update.py` ensure the SQLAlchemy tables exist before writing.
