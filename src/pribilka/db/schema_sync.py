import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Safe additive migrations for deployments that use create_all without Alembic.
_SCHEMA_PATCHES = (
    "ALTER TABLE user_alerts ADD COLUMN IF NOT EXISTS minimum_opportunity_score NUMERIC(5, 2)",
    "ALTER TABLE bank_deposits ADD COLUMN IF NOT EXISTS bank_slug VARCHAR(64)",
    "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS group_id UUID",
    "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS match_count INTEGER",
    """
    CREATE TABLE IF NOT EXISTS alert_notified_instruments (
        alert_id UUID NOT NULL REFERENCES user_alerts(id),
        instrument_id UUID NOT NULL,
        last_notified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (alert_id, instrument_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_access_tokens (
        token_hash VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_user_access_tokens_user_id ON user_access_tokens (user_id)",
    "ALTER TABLE alert_notified_instruments ADD COLUMN IF NOT EXISTS last_notified_yield DOUBLE PRECISION",
    "ALTER TABLE alert_notified_instruments ADD COLUMN IF NOT EXISTS last_notified_rank DOUBLE PRECISION",
    "ALTER TABLE device_tokens ADD COLUMN IF NOT EXISTS locale VARCHAR(8)",
    """
    CREATE TABLE IF NOT EXISTS weekly_digests (
        id UUID PRIMARY KEY,
        country VARCHAR(16) NOT NULL,
        week_start DATE NOT NULL,
        week_end DATE NOT NULL,
        content_en JSONB NOT NULL,
        content_pl JSONB NOT NULL,
        source VARCHAR(32) NOT NULL DEFAULT 'template',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (country, week_start)
    )
    """,
)


def apply_schema_patches(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in _SCHEMA_PATCHES:
            conn.execute(text(statement))
    logger.info("Schema patches applied (%d statements)", len(_SCHEMA_PATCHES))
