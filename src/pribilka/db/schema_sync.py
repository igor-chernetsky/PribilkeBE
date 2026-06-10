import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Safe additive migrations for deployments that use create_all without Alembic.
_SCHEMA_PATCHES = (
    "ALTER TABLE user_alerts ADD COLUMN IF NOT EXISTS minimum_opportunity_score NUMERIC(5, 2)",
    "ALTER TABLE bank_deposits ADD COLUMN IF NOT EXISTS bank_slug VARCHAR(64)",
)


def apply_schema_patches(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in _SCHEMA_PATCHES:
            conn.execute(text(statement))
    logger.info("Schema patches applied (%d statements)", len(_SCHEMA_PATCHES))
