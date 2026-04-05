import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None, default: List[str]) -> List[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/nba_stats",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development"))
APP_VERSION = os.getenv("APP_VERSION", "unknown")
AUTO_CREATE_TABLES = _parse_bool(os.getenv("AUTO_CREATE_TABLES"), default=False)
CORS_ORIGINS = _parse_csv(
    os.getenv("CORS_ORIGINS"),
    default=["http://localhost:5173", "http://localhost:3000"],
)
