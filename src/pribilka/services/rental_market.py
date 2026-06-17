from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from pribilka.collectors.pl.rental.cities import POLAND_RENTAL_CITIES, TRACKED_ROOM_COUNTS
from pribilka.models.enums import RentalListingType
from pribilka.models.rental_market_snapshot import RentalMarketSnapshot
from pribilka.models.rental_yield_snapshot import RentalYieldSnapshot
from pribilka.schemas.rental import (
    RentalCityResponse,
    RentalDistributionResponse,
    RentalMarketHistoryResponse,
    RentalMarketOverviewResponse,
    RentalMarketSegmentResponse,
    RentalPriceTrendSeries,
    RentalTrendPoint,
    RentalYieldSegmentResponse,
    RentalYieldTrendSeries,
)


def list_rental_cities() -> list[RentalCityResponse]:
    return [
        RentalCityResponse(slug=city.slug, name_pl=city.name_pl, name_en=city.name_en)
        for city in POLAND_RENTAL_CITIES
    ]


def get_latest_rental_overview(db: Session) -> RentalMarketOverviewResponse:
    latest_period = db.scalar(select(RentalMarketSnapshot.period_start).order_by(desc(RentalMarketSnapshot.period_start)).limit(1))
    if latest_period is None:
        return RentalMarketOverviewResponse(
            cities=list_rental_cities(),
            segments=[],
            yields=[],
            updated_at=None,
        )

    market_rows = db.scalars(
        select(RentalMarketSnapshot)
        .where(RentalMarketSnapshot.period_start == latest_period)
        .order_by(RentalMarketSnapshot.city_slug, RentalMarketSnapshot.room_count, RentalMarketSnapshot.listing_type)
    ).all()
    yield_rows = db.scalars(
        select(RentalYieldSnapshot)
        .where(RentalYieldSnapshot.period_start == latest_period)
        .order_by(RentalYieldSnapshot.city_slug, RentalYieldSnapshot.room_count)
    ).all()

    return RentalMarketOverviewResponse(
        cities=list_rental_cities(),
        segments=[_market_segment(row) for row in market_rows],
        yields=[_yield_segment(row) for row in yield_rows],
        updated_at=latest_period,
    )


def get_rental_market_history(db: Session, *, days: int = 30) -> RentalMarketHistoryResponse:
    since = datetime.now(UTC) - timedelta(days=days)
    market_rows = db.scalars(
        select(RentalMarketSnapshot)
        .where(RentalMarketSnapshot.period_start >= since)
        .order_by(RentalMarketSnapshot.period_start)
    ).all()
    yield_rows = db.scalars(
        select(RentalYieldSnapshot)
        .where(RentalYieldSnapshot.period_start >= since)
        .order_by(RentalYieldSnapshot.period_start)
    ).all()

    sale_prices: list[RentalPriceTrendSeries] = []
    rent_prices: list[RentalPriceTrendSeries] = []
    for city in POLAND_RENTAL_CITIES:
        for room_count in TRACKED_ROOM_COUNTS:
            sale_points = [
                RentalTrendPoint(
                    period_start=row.period_start,
                    p25=float(row.price_p25) if row.price_p25 is not None else None,
                    median=float(row.price_median) if row.price_median is not None else None,
                    p75=float(row.price_p75) if row.price_p75 is not None else None,
                    sample_size=row.sample_size,
                )
                for row in market_rows
                if row.city_slug == city.slug
                and row.room_count == room_count
                and row.listing_type == RentalListingType.SALE
            ]
            rent_points = [
                RentalTrendPoint(
                    period_start=row.period_start,
                    p25=float(row.price_p25) if row.price_p25 is not None else None,
                    median=float(row.price_median) if row.price_median is not None else None,
                    p75=float(row.price_p75) if row.price_p75 is not None else None,
                    sample_size=row.sample_size,
                )
                for row in market_rows
                if row.city_slug == city.slug
                and row.room_count == room_count
                and row.listing_type == RentalListingType.RENT
            ]
            if sale_points:
                sale_prices.append(
                    RentalPriceTrendSeries(
                        city_slug=city.slug,
                        room_count=room_count,
                        listing_type=RentalListingType.SALE,
                        points=sale_points,
                    )
                )
            if rent_points:
                rent_prices.append(
                    RentalPriceTrendSeries(
                        city_slug=city.slug,
                        room_count=room_count,
                        listing_type=RentalListingType.RENT,
                        points=rent_points,
                    )
                )

    gross_yields: list[RentalYieldTrendSeries] = []
    for city in POLAND_RENTAL_CITIES:
        for room_count in TRACKED_ROOM_COUNTS:
            points = [
                RentalTrendPoint(
                    period_start=row.period_start,
                    p25=float(row.gross_yield_p25) if row.gross_yield_p25 is not None else None,
                    median=float(row.gross_yield_median) if row.gross_yield_median is not None else None,
                    p75=float(row.gross_yield_p75) if row.gross_yield_p75 is not None else None,
                    sample_size=min(row.sale_sample_size, row.rent_sample_size),
                )
                for row in yield_rows
                if row.city_slug == city.slug and row.room_count == room_count
            ]
            if points:
                gross_yields.append(
                    RentalYieldTrendSeries(
                        city_slug=city.slug,
                        room_count=room_count,
                        points=points,
                    )
                )

    return RentalMarketHistoryResponse(
        days=days,
        sale_prices=sale_prices,
        rent_prices=rent_prices,
        gross_yields=gross_yields,
    )


def _market_segment(row: RentalMarketSnapshot) -> RentalMarketSegmentResponse:
    return RentalMarketSegmentResponse(
        city_slug=row.city_slug,
        listing_type=row.listing_type,
        room_count=row.room_count,
        period_start=row.period_start,
        prices=RentalDistributionResponse(
            sample_size=row.sample_size,
            p25=float(row.price_p25) if row.price_p25 is not None else None,
            median=float(row.price_median) if row.price_median is not None else None,
            p75=float(row.price_p75) if row.price_p75 is not None else None,
        ),
        price_per_sqm=RentalDistributionResponse(
            sample_size=row.sample_size,
            p25=float(row.price_per_sqm_p25) if row.price_per_sqm_p25 is not None else None,
            median=float(row.price_per_sqm_median) if row.price_per_sqm_median is not None else None,
            p75=float(row.price_per_sqm_p75) if row.price_per_sqm_p75 is not None else None,
        ),
    )


def _yield_segment(row: RentalYieldSnapshot) -> RentalYieldSegmentResponse:
    return RentalYieldSegmentResponse(
        city_slug=row.city_slug,
        room_count=row.room_count,
        period_start=row.period_start,
        sale_sample_size=row.sale_sample_size,
        rent_sample_size=row.rent_sample_size,
        sale_price_median=float(row.sale_price_median) if row.sale_price_median is not None else None,
        rent_price_median=float(row.rent_price_median) if row.rent_price_median is not None else None,
        gross_yield=RentalDistributionResponse(
            sample_size=min(row.sale_sample_size, row.rent_sample_size),
            p25=float(row.gross_yield_p25) if row.gross_yield_p25 is not None else None,
            median=float(row.gross_yield_median) if row.gross_yield_median is not None else None,
            p75=float(row.gross_yield_p75) if row.gross_yield_p75 is not None else None,
        ),
    )
