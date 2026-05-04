import logging

import app.models
from app.config import AUTO_CREATE_TABLES
from app.db import Base, engine


logger = logging.getLogger(__name__)


def ensure_tables_if_enabled() -> None:
    if not AUTO_CREATE_TABLES:
        return

    logger.info("AUTO_CREATE_TABLES enabled, ensuring database tables exist")
    Base.metadata.create_all(bind=engine)
