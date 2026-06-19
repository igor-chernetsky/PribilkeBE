from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pribilka.db.base import Base
from pribilka.models.enums import RentalListingType
from pribilka.models.rental_market_snapshot import RentalMarketSnapshot
from pribilka.models.rental_yield_snapshot import RentalYieldSnapshot
from pribilka.services.rental_weekly_stats import collect_rental_weekly_stats

_RENTAL_TABLES = (
    RentalMarketSnapshot.__table__,
    RentalYieldSnapshot.__table__,
)


def _make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=list(_RENTAL_TABLES))
    return sessionmaker(bind=engine)()


def test_collect_rental_weekly_stats_returns_city_highlights():
    db = _make_session()
    now = datetime.now(UTC)
    earlier = now - timedelta(days=5)
    later = now - timedelta(days=1)

    for period, sale_price, rent_price, gross_yield in (
        (earlier, 600_000, 2_500, 4.8),
        (later, 620_000, 2_600, 5.0),
    ):
        db.add(
            RentalMarketSnapshot(
                city_slug="warszawa",
                listing_type=RentalListingType.SALE,
                room_count=2,
                period_start=period,
                sample_size=10,
                price_median=sale_price,
            )
        )
        db.add(
            RentalMarketSnapshot(
                city_slug="warszawa",
                listing_type=RentalListingType.RENT,
                room_count=2,
                period_start=period,
                sample_size=10,
                price_median=rent_price,
            )
        )
        db.add(
            RentalYieldSnapshot(
                city_slug="warszawa",
                room_count=2,
                period_start=period,
                sale_sample_size=10,
                rent_sample_size=10,
                sale_price_median=sale_price,
                rent_price_median=rent_price,
                gross_yield_median=gross_yield,
            )
        )
        db.add(
            RentalYieldSnapshot(
                city_slug="krakow",
                room_count=2,
                period_start=period,
                sale_sample_size=8,
                rent_sample_size=8,
                sale_price_median=500_000,
                rent_price_median=2_400,
                gross_yield_median=5.5 if period == later else 5.3,
            )
        )
    db.commit()

    stats = collect_rental_weekly_stats(db, days=7)

    assert stats["available"] is True
    assert stats["snapshot_periods"] == 2
    assert stats["top_yield_cities"][0]["city_slug"] == "krakow"
    warsaw = next(city for city in stats["cities"] if city["city_slug"] == "warszawa")
    assert warsaw["yield_now"] == 5.0
    assert warsaw["yield_start"] == 4.8
    assert warsaw["sale_median_now"] == 620_000
    assert warsaw["rent_median_delta"] == 100

    db.close()


def test_collect_rental_weekly_stats_empty_when_no_snapshots():
    db = _make_session()
    stats = collect_rental_weekly_stats(db, days=7)
    assert stats["available"] is False
    assert stats["snapshot_periods"] == 0
    db.close()
