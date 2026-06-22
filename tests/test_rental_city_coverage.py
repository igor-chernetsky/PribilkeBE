from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pribilka.db.base import Base
from pribilka.models.enums import RentalListingType
from pribilka.models.rental_listing import RentalListing
from pribilka.models.rental_market_snapshot import RentalMarketSnapshot
from pribilka.models.rental_yield_snapshot import RentalYieldSnapshot
from pribilka.services.rental_city_coverage import assess_rental_city_coverage
from pribilka.services.rental_ingestion import ingest_rental_listings
from pribilka.services.rental_stats import truncate_to_12h_period

_RENTAL_TABLES = (
    RentalListing.__table__,
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


def test_ingest_only_updates_snapshots_for_requested_cities():
    db = _make_session()
    now = datetime(2026, 6, 7, 13, 0, tzinfo=UTC)
    records = [
        {
            "source": "otodom",
            "external_id": "sale-1",
            "listing_type": RentalListingType.SALE,
            "city_slug": "lublin",
            "room_count": 2,
            "price_pln": 450_000,
            "area_sqm": 50,
            "price_per_sqm": 9_000,
            "title": "Sale 1",
            "url": "https://example.com/sale-1",
            "published_at": now,
        },
        {
            "source": "otodom",
            "external_id": "rent-1",
            "listing_type": RentalListingType.RENT,
            "city_slug": "lublin",
            "room_count": 2,
            "price_pln": 2_200,
            "area_sqm": 48,
            "price_per_sqm": 45,
            "title": "Rent 1",
            "url": "https://example.com/rent-1",
            "published_at": now,
        },
    ]

    ingest_rental_listings(db, records, city_slugs=["lublin"])
    period_start = truncate_to_12h_period(datetime.now(UTC))

    lublin_sale = db.scalar(
        select(RentalMarketSnapshot).where(
            RentalMarketSnapshot.city_slug == "lublin",
            RentalMarketSnapshot.listing_type == RentalListingType.SALE,
            RentalMarketSnapshot.room_count == 2,
            RentalMarketSnapshot.period_start == period_start,
        )
    )
    warsaw_sale = db.scalar(
        select(RentalMarketSnapshot).where(
            RentalMarketSnapshot.city_slug == "warszawa",
            RentalMarketSnapshot.listing_type == RentalListingType.SALE,
            RentalMarketSnapshot.room_count == 2,
            RentalMarketSnapshot.period_start == period_start,
        )
    )

    assert lublin_sale is not None
    assert lublin_sale.sample_size == 1
    assert warsaw_sale is None

    db.close()


def test_assess_rental_city_coverage_flags_missing_city():
    db = _make_session()
    now = datetime(2026, 6, 7, 13, 0, tzinfo=UTC)
    ingest_rental_listings(
        db,
        [
            {
                "source": "otodom",
                "external_id": "sale-1",
                "listing_type": RentalListingType.SALE,
                "city_slug": "warszawa",
                "room_count": 2,
                "price_pln": 600_000,
                "area_sqm": 50,
                "price_per_sqm": 12_000,
                "title": "Sale 1",
                "url": "https://example.com/sale-1",
                "published_at": now,
            }
        ],
        city_slugs=["warszawa"],
    )

    gaps = assess_rental_city_coverage(
        db,
        ["warszawa", "lublin"],
        records_by_city={"warszawa": 1, "lublin": 0},
    )

    assert len(gaps) == 2
    lublin_gap = next(gap for gap in gaps if gap.city_slug == "lublin")
    assert lublin_gap.missing_sale is True
    assert lublin_gap.missing_rent is True
    assert lublin_gap.records_collected == 0

    db.close()
