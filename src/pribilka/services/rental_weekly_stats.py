from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.collectors.pl.rental.cities import POLAND_RENTAL_CITIES
from pribilka.models.enums import RentalListingType
from pribilka.models.rental_market_snapshot import RentalMarketSnapshot
from pribilka.models.rental_yield_snapshot import RentalYieldSnapshot

_DIGEST_ROOM_COUNT = 2


def _series_endpoints(
    rows: list,
    value_attr: str,
) -> tuple[float | None, float | None, float | None]:
    values = [
        (row.period_start, float(getattr(row, value_attr)))
        for row in rows
        if getattr(row, value_attr) is not None
    ]
    if not values:
        return None, None, None
    values.sort(key=lambda item: item[0])
    start_val = values[0][1]
    end_val = values[-1][1]
    return end_val, start_val, end_val - start_val


def collect_rental_weekly_stats(db: Session, *, days: int = 7) -> dict:
    since = datetime.now(UTC) - timedelta(days=days)

    yield_rows = list(
        db.scalars(
            select(RentalYieldSnapshot)
            .where(RentalYieldSnapshot.period_start >= since)
            .order_by(RentalYieldSnapshot.period_start)
        ).all()
    )
    market_rows = list(
        db.scalars(
            select(RentalMarketSnapshot)
            .where(RentalMarketSnapshot.period_start >= since)
            .order_by(RentalMarketSnapshot.period_start)
        ).all()
    )

    period_starts = sorted(
        {row.period_start for row in yield_rows} | {row.period_start for row in market_rows}
    )
    if not period_starts:
        return {"available": False, "snapshot_periods": 0, "cities": [], "top_yield_cities": []}

    cities: list[dict] = []
    for city in POLAND_RENTAL_CITIES:
        city_yields = [
            row
            for row in yield_rows
            if row.city_slug == city.slug and row.room_count == _DIGEST_ROOM_COUNT
        ]
        sale_rows = [
            row
            for row in market_rows
            if row.city_slug == city.slug
            and row.room_count == _DIGEST_ROOM_COUNT
            and row.listing_type == RentalListingType.SALE
        ]
        rent_rows = [
            row
            for row in market_rows
            if row.city_slug == city.slug
            and row.room_count == _DIGEST_ROOM_COUNT
            and row.listing_type == RentalListingType.RENT
        ]

        yield_now, yield_start, yield_delta = _series_endpoints(city_yields, "gross_yield_median")
        if yield_now is None:
            continue

        sale_now, sale_start, sale_delta = _series_endpoints(sale_rows, "price_median")
        rent_now, rent_start, rent_delta = _series_endpoints(rent_rows, "price_median")

        cities.append(
            {
                "city_slug": city.slug,
                "name_pl": city.name_pl,
                "name_en": city.name_en,
                "room_count": _DIGEST_ROOM_COUNT,
                "yield_now": yield_now,
                "yield_start": yield_start,
                "yield_delta_pp": yield_delta,
                "sale_median_now": sale_now,
                "sale_median_start": sale_start,
                "sale_median_delta": sale_delta,
                "rent_median_now": rent_now,
                "rent_median_start": rent_start,
                "rent_median_delta": rent_delta,
            }
        )

    cities.sort(key=lambda item: item["yield_now"], reverse=True)

    return {
        "available": bool(cities),
        "snapshot_periods": len(period_starts),
        "room_count": _DIGEST_ROOM_COUNT,
        "cities": cities,
        "top_yield_cities": cities[:3],
    }
