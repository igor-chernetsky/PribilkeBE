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
    """
    CREATE TABLE IF NOT EXISTS rental_listings (
        id UUID PRIMARY KEY,
        source VARCHAR(32) NOT NULL DEFAULT 'otodom',
        external_id VARCHAR(64) NOT NULL,
        listing_type VARCHAR(16) NOT NULL,
        city_slug VARCHAR(64) NOT NULL,
        room_count INTEGER NOT NULL,
        price_pln NUMERIC(12, 2) NOT NULL,
        area_sqm NUMERIC(8, 2),
        price_per_sqm NUMERIC(10, 2),
        title VARCHAR(512),
        url VARCHAR(1024),
        published_at TIMESTAMPTZ,
        first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (source, external_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_rental_listings_city_slug ON rental_listings (city_slug)",
    "CREATE INDEX IF NOT EXISTS ix_rental_listings_last_seen_at ON rental_listings (last_seen_at)",
    "CREATE INDEX IF NOT EXISTS ix_rental_listings_fresh_lookup ON rental_listings (city_slug, listing_type, room_count, last_seen_at)",
    """
    CREATE TABLE IF NOT EXISTS rental_market_snapshots (
        id UUID PRIMARY KEY,
        city_slug VARCHAR(64) NOT NULL,
        listing_type VARCHAR(16) NOT NULL,
        room_count INTEGER NOT NULL,
        period_start TIMESTAMPTZ NOT NULL,
        sample_size INTEGER NOT NULL DEFAULT 0,
        price_p25 NUMERIC(12, 2),
        price_median NUMERIC(12, 2),
        price_p75 NUMERIC(12, 2),
        price_per_sqm_p25 NUMERIC(10, 2),
        price_per_sqm_median NUMERIC(10, 2),
        price_per_sqm_p75 NUMERIC(10, 2),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (city_slug, listing_type, room_count, period_start)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_rental_market_snapshots_city_slug ON rental_market_snapshots (city_slug)",
    "CREATE INDEX IF NOT EXISTS ix_rental_market_snapshots_period_start ON rental_market_snapshots (period_start)",
    """
    CREATE TABLE IF NOT EXISTS rental_yield_snapshots (
        id UUID PRIMARY KEY,
        city_slug VARCHAR(64) NOT NULL,
        room_count INTEGER NOT NULL,
        period_start TIMESTAMPTZ NOT NULL,
        sale_sample_size INTEGER NOT NULL DEFAULT 0,
        rent_sample_size INTEGER NOT NULL DEFAULT 0,
        sale_price_median NUMERIC(12, 2),
        rent_price_median NUMERIC(12, 2),
        gross_yield_p25 NUMERIC(6, 3),
        gross_yield_median NUMERIC(6, 3),
        gross_yield_p75 NUMERIC(6, 3),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (city_slug, room_count, period_start)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_rental_yield_snapshots_city_slug ON rental_yield_snapshots (city_slug)",
    "CREATE INDEX IF NOT EXISTS ix_rental_yield_snapshots_period_start ON rental_yield_snapshots (period_start)",
    """
    CREATE TABLE IF NOT EXISTS macro_indicators (
        id UUID PRIMARY KEY,
        country VARCHAR(16) NOT NULL,
        kind VARCHAR(32) NOT NULL,
        value NUMERIC(8, 4) NOT NULL,
        as_of_date DATE NOT NULL,
        source_name VARCHAR(64) NOT NULL,
        source_url VARCHAR(512),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_macro_country_kind_date UNIQUE (country, kind, as_of_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_macro_indicators_country ON macro_indicators (country)",
    "CREATE INDEX IF NOT EXISTS ix_macro_indicators_kind ON macro_indicators (kind)",
    "CREATE INDEX IF NOT EXISTS ix_macro_indicators_as_of_date ON macro_indicators (as_of_date)",
)


def apply_schema_patches(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in _SCHEMA_PATCHES:
            conn.execute(text(statement))
    logger.info("Schema patches applied (%d statements)", len(_SCHEMA_PATCHES))
