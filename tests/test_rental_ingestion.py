from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pribilka.db.base import Base
from pribilka.models.enums import RentalListingType
from pribilka.models.rental_listing import RentalListing
from pribilka.models.rental_market_snapshot import RentalMarketSnapshot
from pribilka.models.rental_yield_snapshot import RentalYieldSnapshot
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


def test_ingest_rental_listings_writes_snapshots():
    db = _make_session()
    now = datetime(2026, 6, 7, 13, 0, tzinfo=UTC)
    records = [
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
        },
        {
            "source": "otodom",
            "external_id": "sale-2",
            "listing_type": RentalListingType.SALE,
            "city_slug": "warszawa",
            "room_count": 2,
            "price_pln": 700_000,
            "area_sqm": 55,
            "price_per_sqm": 12_727,
            "title": "Sale 2",
            "url": "https://example.com/sale-2",
            "published_at": now,
        },
        {
            "source": "otodom",
            "external_id": "rent-1",
            "listing_type": RentalListingType.RENT,
            "city_slug": "warszawa",
            "room_count": 2,
            "price_pln": 2_500,
            "area_sqm": 48,
            "price_per_sqm": 52,
            "title": "Rent 1",
            "url": "https://example.com/rent-1",
            "published_at": now,
        },
        {
            "source": "otodom",
            "external_id": "rent-2",
            "listing_type": RentalListingType.RENT,
            "city_slug": "warszawa",
            "room_count": 2,
            "price_pln": 3_000,
            "area_sqm": 52,
            "price_per_sqm": 57,
            "title": "Rent 2",
            "url": "https://example.com/rent-2",
            "published_at": now,
        },
    ]

    ingested = ingest_rental_listings(db, records)
    assert ingested == 4

    period_start = truncate_to_12h_period(datetime.now(UTC))
    sale_snapshot = db.scalar(
        select(RentalMarketSnapshot).where(
            RentalMarketSnapshot.city_slug == "warszawa",
            RentalMarketSnapshot.listing_type == RentalListingType.SALE,
            RentalMarketSnapshot.room_count == 2,
            RentalMarketSnapshot.period_start == period_start,
        )
    )
    assert sale_snapshot is not None
    assert sale_snapshot.sample_size == 2
    assert float(sale_snapshot.price_median) == 650_000

    yield_snapshot = db.scalar(
        select(RentalYieldSnapshot).where(
            RentalYieldSnapshot.city_slug == "warszawa",
            RentalYieldSnapshot.room_count == 2,
            RentalYieldSnapshot.period_start == period_start,
        )
    )
    assert yield_snapshot is not None
    assert yield_snapshot.sale_sample_size == 2
    assert yield_snapshot.rent_sample_size == 2
    assert yield_snapshot.gross_yield_median is not None

    db.close()


def test_ingest_preserves_snapshot_when_refresh_is_empty():
    db = _make_session()
    now = datetime(2026, 6, 7, 13, 0, tzinfo=UTC)
    records = [
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
        },
    ]

    ingest_rental_listings(db, records)
    period_start = truncate_to_12h_period(datetime.now(UTC))
    before = db.scalar(
        select(RentalMarketSnapshot).where(
            RentalMarketSnapshot.city_slug == "warszawa",
            RentalMarketSnapshot.listing_type == RentalListingType.SALE,
            RentalMarketSnapshot.room_count == 2,
            RentalMarketSnapshot.period_start == period_start,
        )
    )
    assert before is not None
    assert before.sample_size == 1
    assert float(before.price_median) == 600_000

    ingest_rental_listings(db, [])
    after = db.scalar(
        select(RentalMarketSnapshot).where(
            RentalMarketSnapshot.city_slug == "warszawa",
            RentalMarketSnapshot.listing_type == RentalListingType.SALE,
            RentalMarketSnapshot.room_count == 2,
            RentalMarketSnapshot.period_start == period_start,
        )
    )
    assert after is not None
    assert after.sample_size == 1
    assert float(after.price_median) == 600_000

    db.close()


def test_ingest_revives_stale_listing_without_stale_data_error():
    """Stale listing re-collected must not be deleted by purge before flush."""
    from datetime import timedelta

    db = _make_session()
    stale_at = datetime.now(UTC) - timedelta(hours=72)
    now = datetime.now(UTC)

    db.add(
        RentalListing(
            source="otodom",
            external_id="stale-sale-1",
            listing_type=RentalListingType.SALE,
            city_slug="lublin",
            room_count=2,
            price_pln=500_000,
            first_seen_at=stale_at,
            last_seen_at=stale_at,
        )
    )
    db.commit()

    records = [
        {
            "source": "otodom",
            "external_id": "stale-sale-1",
            "listing_type": RentalListingType.SALE,
            "city_slug": "lublin",
            "room_count": 2,
            "price_pln": 510_000,
            "area_sqm": 50,
            "price_per_sqm": 10_200,
            "title": "Sale refreshed",
            "url": "https://example.com/stale-sale-1",
            "published_at": now,
        },
    ]

    ingested = ingest_rental_listings(db, records, city_slugs=["lublin"])
    assert ingested == 1

    listing = db.scalar(
        select(RentalListing).where(
            RentalListing.source == "otodom",
            RentalListing.external_id == "stale-sale-1",
        )
    )
    assert listing is not None
    assert float(listing.price_pln) == 510_000
    seen_at = listing.last_seen_at
    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=UTC)
    assert seen_at >= now - timedelta(minutes=1)

    period_start = truncate_to_12h_period(datetime.now(UTC))
    snapshot = db.scalar(
        select(RentalMarketSnapshot).where(
            RentalMarketSnapshot.city_slug == "lublin",
            RentalMarketSnapshot.listing_type == RentalListingType.SALE,
            RentalMarketSnapshot.room_count == 2,
            RentalMarketSnapshot.period_start == period_start,
        )
    )
    assert snapshot is not None
    assert snapshot.sample_size == 1

    db.close()


def test_ingest_dedupes_duplicate_external_ids_in_one_batch():
    db = _make_session()
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)
    records = [
        {
            "source": "otodom",
            "external_id": "68081516",
            "listing_type": RentalListingType.SALE,
            "city_slug": "lublin",
            "room_count": 2,
            "price_pln": 500_000,
            "area_sqm": 50,
            "price_per_sqm": 10_000,
            "title": "First copy",
            "url": "https://example.com/68081516",
            "published_at": now,
        },
        {
            "source": "otodom",
            "external_id": "68081516",
            "listing_type": RentalListingType.SALE,
            "city_slug": "lublin",
            "room_count": 2,
            "price_pln": 510_000,
            "area_sqm": 50,
            "price_per_sqm": 10_200,
            "title": "Second copy",
            "url": "https://example.com/68081516-v2",
            "published_at": now,
        },
    ]

    ingested = ingest_rental_listings(db, records, city_slugs=["lublin"])
    assert ingested == 1

    listing = db.scalar(
        select(RentalListing).where(
            RentalListing.source == "otodom",
            RentalListing.external_id == "68081516",
        )
    )
    assert listing is not None
    assert float(listing.price_pln) == 510_000
    assert listing.title == "Second copy"

    db.close()
