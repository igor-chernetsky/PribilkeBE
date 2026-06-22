from __future__ import annotations

import logging
from datetime import UTC, datetime

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pribilka.collectors.pl.rental.cities import POLAND_RENTAL_CITIES, TRACKED_ROOM_COUNTS
from pribilka.models.enums import RentalListingType
from pribilka.models.rental_listing import RentalListing
from pribilka.models.rental_market_snapshot import RentalMarketSnapshot
from pribilka.models.rental_yield_snapshot import RentalYieldSnapshot
from pribilka.services.rental_stats import (
    DistributionStats,
    fresh_cutoff,
    truncate_to_12h_period,
    yield_stats,
    distribution_stats,
)

logger = logging.getLogger(__name__)

FRESH_LISTING_MAX_AGE_HOURS = 48


def ingest_rental_listings(
    db: Session,
    records: list[dict],
    *,
    city_slugs: Sequence[str] | None = None,
) -> int:
    now = datetime.now(UTC)
    period_start = truncate_to_12h_period(now)
    upserted = _upsert_listings(db, records, now=now)
    # Flush before purge so refreshed listings persist last_seen_at in DB.
    # Otherwise purge deletes rows that upsert just revived (>48h stale),
    # and commit fails with "expected to update N row(s); 0 were matched".
    db.flush()
    removed = _purge_stale_listings(db, now=now)
    snapshots = _write_market_snapshots(
        db, period_start=period_start, now=now, city_slugs=city_slugs
    )
    yields = _write_yield_snapshots(
        db, period_start=period_start, now=now, city_slugs=city_slugs
    )
    db.commit()
    logger.info(
        "Rental ingest: upserted=%d removed=%d market_snapshots=%d yield_snapshots=%d",
        upserted,
        removed,
        snapshots,
        yields,
    )
    return upserted


def refresh_rental_snapshots_from_listings(db: Session) -> dict[str, int]:
    """Recompute market/yield snapshots from listings already stored in the DB."""
    now = datetime.now(UTC)
    period_start = truncate_to_12h_period(now)
    market = _write_market_snapshots(db, period_start=period_start, now=now, city_slugs=None)
    yields = _write_yield_snapshots(db, period_start=period_start, now=now, city_slugs=None)
    db.commit()
    return {"market_snapshots": market, "yield_snapshots": yields}


def _upsert_listings(db: Session, records: list[dict], *, now: datetime) -> int:
    count = 0
    for record in records:
        listing_type = record["listing_type"]
        if isinstance(listing_type, str):
            listing_type = RentalListingType(listing_type)

        existing = db.scalar(
            select(RentalListing).where(
                RentalListing.source == record["source"],
                RentalListing.external_id == record["external_id"],
            )
        )
        if existing is None:
            db.add(
                RentalListing(
                    source=record["source"],
                    external_id=record["external_id"],
                    listing_type=listing_type,
                    city_slug=record["city_slug"],
                    room_count=record["room_count"],
                    price_pln=record["price_pln"],
                    area_sqm=record.get("area_sqm"),
                    price_per_sqm=record.get("price_per_sqm"),
                    title=record.get("title"),
                    url=record.get("url"),
                    published_at=record.get("published_at"),
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )
        else:
            existing.listing_type = listing_type
            existing.city_slug = record["city_slug"]
            existing.room_count = record["room_count"]
            existing.price_pln = record["price_pln"]
            existing.area_sqm = record.get("area_sqm")
            existing.price_per_sqm = record.get("price_per_sqm")
            existing.title = record.get("title")
            existing.url = record.get("url")
            if record.get("published_at"):
                existing.published_at = record["published_at"]
            existing.last_seen_at = now
        count += 1
    return count


def _purge_stale_listings(db: Session, *, now: datetime) -> int:
    cutoff = fresh_cutoff(now, max_age_hours=FRESH_LISTING_MAX_AGE_HOURS)
    result = db.execute(delete(RentalListing).where(RentalListing.last_seen_at < cutoff))
    return result.rowcount or 0


def _fresh_listings(
    db: Session,
    *,
    city_slug: str,
    listing_type: RentalListingType,
    room_count: int,
    now: datetime,
) -> list[RentalListing]:
    cutoff = fresh_cutoff(now, max_age_hours=FRESH_LISTING_MAX_AGE_HOURS)
    return list(
        db.scalars(
            select(RentalListing).where(
                RentalListing.city_slug == city_slug,
                RentalListing.listing_type == listing_type,
                RentalListing.room_count == room_count,
                RentalListing.last_seen_at >= cutoff,
            )
        ).all()
    )


def _keep_existing_market_snapshot(
    snapshot: RentalMarketSnapshot | None,
    price_stats: DistributionStats,
) -> bool:
    """Avoid wiping a populated snapshot when a refresh finds no fresh listings."""
    if price_stats.sample_size > 0:
        return False
    return snapshot is not None and snapshot.sample_size > 0


def _keep_existing_yield_snapshot(
    snapshot: RentalYieldSnapshot | None,
    sale_sample_size: int,
    rent_sample_size: int,
) -> bool:
    if sale_sample_size > 0 or rent_sample_size > 0:
        return False
    if snapshot is None:
        return False
    return snapshot.sale_sample_size > 0 or snapshot.rent_sample_size > 0


def _iter_snapshot_cities(city_slugs: Sequence[str] | None):
    if city_slugs is None:
        yield from POLAND_RENTAL_CITIES
        return
    allowed = set(city_slugs)
    for city in POLAND_RENTAL_CITIES:
        if city.slug in allowed:
            yield city


def _write_market_snapshots(
    db: Session,
    *,
    period_start: datetime,
    now: datetime,
    city_slugs: Sequence[str] | None,
) -> int:
    written = 0
    for city in _iter_snapshot_cities(city_slugs):
        for room_count in TRACKED_ROOM_COUNTS:
            for listing_type in (RentalListingType.SALE, RentalListingType.RENT):
                listings = _fresh_listings(
                    db,
                    city_slug=city.slug,
                    listing_type=listing_type,
                    room_count=room_count,
                    now=now,
                )
                price_stats = distribution_stats([float(item.price_pln) for item in listings])
                sqm_values = [
                    float(item.price_per_sqm)
                    for item in listings
                    if item.price_per_sqm is not None and item.price_per_sqm > 0
                ]
                sqm_stats = distribution_stats(sqm_values)

                snapshot = db.scalar(
                    select(RentalMarketSnapshot).where(
                        RentalMarketSnapshot.city_slug == city.slug,
                        RentalMarketSnapshot.listing_type == listing_type,
                        RentalMarketSnapshot.room_count == room_count,
                        RentalMarketSnapshot.period_start == period_start,
                    )
                )
                if _keep_existing_market_snapshot(snapshot, price_stats):
                    continue
                if snapshot is None:
                    snapshot = RentalMarketSnapshot(
                        city_slug=city.slug,
                        listing_type=listing_type,
                        room_count=room_count,
                        period_start=period_start,
                    )
                    db.add(snapshot)

                snapshot.sample_size = price_stats.sample_size
                snapshot.price_p25 = price_stats.p25
                snapshot.price_median = price_stats.median
                snapshot.price_p75 = price_stats.p75
                snapshot.price_per_sqm_p25 = sqm_stats.p25
                snapshot.price_per_sqm_median = sqm_stats.median
                snapshot.price_per_sqm_p75 = sqm_stats.p75
                written += 1
    return written


def _write_yield_snapshots(
    db: Session,
    *,
    period_start: datetime,
    now: datetime,
    city_slugs: Sequence[str] | None,
) -> int:
    written = 0
    for city in _iter_snapshot_cities(city_slugs):
        for room_count in TRACKED_ROOM_COUNTS:
            sale_listings = _fresh_listings(
                db,
                city_slug=city.slug,
                listing_type=RentalListingType.SALE,
                room_count=room_count,
                now=now,
            )
            rent_listings = _fresh_listings(
                db,
                city_slug=city.slug,
                listing_type=RentalListingType.RENT,
                room_count=room_count,
                now=now,
            )
            stats = yield_stats(
                [float(item.price_pln) for item in sale_listings],
                [float(item.price_pln) for item in rent_listings],
            )

            snapshot = db.scalar(
                select(RentalYieldSnapshot).where(
                    RentalYieldSnapshot.city_slug == city.slug,
                    RentalYieldSnapshot.room_count == room_count,
                    RentalYieldSnapshot.period_start == period_start,
                )
            )
            if _keep_existing_yield_snapshot(
                snapshot,
                stats.sale_sample_size,
                stats.rent_sample_size,
            ):
                continue
            if snapshot is None:
                snapshot = RentalYieldSnapshot(
                    city_slug=city.slug,
                    room_count=room_count,
                    period_start=period_start,
                )
                db.add(snapshot)

            snapshot.sale_sample_size = stats.sale_sample_size
            snapshot.rent_sample_size = stats.rent_sample_size
            snapshot.sale_price_median = stats.sale_price_median
            snapshot.rent_price_median = stats.rent_price_median
            snapshot.gross_yield_p25 = stats.gross_yield_p25
            snapshot.gross_yield_median = stats.gross_yield_median
            snapshot.gross_yield_p75 = stats.gross_yield_p75
            written += 1
    return written
