from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from pribilka.collectors.pl.rental.cities import POLAND_RENTAL_CITIES
from pribilka.models.enums import RentalListingType
from pribilka.models.rental_listing import RentalListing
from pribilka.models.rental_market_snapshot import RentalMarketSnapshot
from pribilka.models.rental_yield_snapshot import RentalYieldSnapshot
from pribilka.services.rental_stats import fresh_cutoff, truncate_to_12h_period


@dataclass(frozen=True)
class RentalCityDataGap:
    city_slug: str
    name_pl: str
    missing_sale: bool
    missing_rent: bool
    missing_yield: bool
    listing_count: int
    records_collected: int


def _latest_snapshot_period(db: Session) -> datetime | None:
    return db.scalar(select(RentalMarketSnapshot.period_start).order_by(desc(RentalMarketSnapshot.period_start)).limit(1))


def _fresh_listing_count(db: Session, *, city_slug: str, now: datetime) -> int:
    cutoff = fresh_cutoff(now, max_age_hours=48)
    return (
        db.scalar(
            select(func.count())
            .select_from(RentalListing)
            .where(
                RentalListing.city_slug == city_slug,
                RentalListing.last_seen_at >= cutoff,
            )
        )
        or 0
    )


def _has_market_median(
    db: Session,
    *,
    city_slug: str,
    listing_type: RentalListingType,
    period_start: datetime,
) -> bool:
    count = db.scalar(
        select(func.count())
        .select_from(RentalMarketSnapshot)
        .where(
            RentalMarketSnapshot.city_slug == city_slug,
            RentalMarketSnapshot.listing_type == listing_type,
            RentalMarketSnapshot.period_start == period_start,
            RentalMarketSnapshot.sample_size > 0,
            RentalMarketSnapshot.price_median.is_not(None),
        )
    )
    return bool(count)


def _has_yield_median(db: Session, *, city_slug: str, period_start: datetime) -> bool:
    count = db.scalar(
        select(func.count())
        .select_from(RentalYieldSnapshot)
        .where(
            RentalYieldSnapshot.city_slug == city_slug,
            RentalYieldSnapshot.period_start == period_start,
            RentalYieldSnapshot.gross_yield_median.is_not(None),
        )
    )
    return bool(count)


def assess_rental_city_coverage(
    db: Session,
    city_slugs: Sequence[str],
    *,
    records_by_city: dict[str, int] | None = None,
    now: datetime | None = None,
) -> list[RentalCityDataGap]:
    """Return cities from *city_slugs* that lack usable snapshot medians."""
    now = now or datetime.now(UTC)
    period_start = _latest_snapshot_period(db) or truncate_to_12h_period(now)
    records_by_city = records_by_city or {}
    city_lookup = {city.slug: city for city in POLAND_RENTAL_CITIES}
    gaps: list[RentalCityDataGap] = []

    for city_slug in city_slugs:
        city = city_lookup.get(city_slug)
        if city is None:
            continue

        missing_sale = not _has_market_median(
            db, city_slug=city_slug, listing_type=RentalListingType.SALE, period_start=period_start
        )
        missing_rent = not _has_market_median(
            db, city_slug=city_slug, listing_type=RentalListingType.RENT, period_start=period_start
        )
        missing_yield = not _has_yield_median(db, city_slug=city_slug, period_start=period_start)

        if not (missing_sale or missing_rent or missing_yield):
            continue

        gaps.append(
            RentalCityDataGap(
                city_slug=city_slug,
                name_pl=city.name_pl,
                missing_sale=missing_sale,
                missing_rent=missing_rent,
                missing_yield=missing_yield,
                listing_count=_fresh_listing_count(db, city_slug=city_slug, now=now),
                records_collected=records_by_city.get(city_slug, 0),
            )
        )

    return gaps
