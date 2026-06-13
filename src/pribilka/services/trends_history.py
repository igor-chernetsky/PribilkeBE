from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pribilka.models.enums import AssetClass, CountryCode
from pribilka.models.financial_instrument import FinancialInstrument
from pribilka.models.rate_history import RateHistory
from pribilka.schemas.trends import (
    GoldTrendSeries,
    MarketTrendsHistoryResponse,
    TrendPoint,
    YieldTrendSeries,
)


def _bucket_expr(days: int):
    unit = "hour" if days <= 7 else "day"
    return func.date_trunc(unit, RateHistory.recorded_at)


def _aggregate_yield_series(
    db: Session,
    *,
    country: CountryCode,
    asset_class: AssetClass,
    value_type: str,
    since: datetime,
    days: int,
) -> YieldTrendSeries:
    bucket = _bucket_expr(days).label("bucket")

    query = (
        select(
            bucket,
            func.max(RateHistory.value).label("best"),
            func.avg(RateHistory.value).label("average"),
        )
        .join(FinancialInstrument, RateHistory.instrument_id == FinancialInstrument.id)
        .where(
            FinancialInstrument.country == country,
            FinancialInstrument.asset_class == asset_class,
            RateHistory.value_type == value_type,
            RateHistory.recorded_at >= since,
        )
        .group_by(bucket)
        .order_by(bucket)
    )

    rows = db.execute(query).all()

    best = [
        TrendPoint(value=float(row.best), recorded_at=row.bucket)
        for row in rows
        if row.best is not None
    ]
    average = [
        TrendPoint(value=float(row.average), recorded_at=row.bucket)
        for row in rows
        if row.average is not None
    ]
    return YieldTrendSeries(best=best, average=average)


def _gold_spot_series(
    db: Session,
    *,
    country: CountryCode,
    since: datetime,
    days: int,
) -> GoldTrendSeries:
    bucket = _bucket_expr(days).label("bucket")

    rows = db.execute(
        select(bucket, func.avg(RateHistory.value).label("spot"))
        .join(FinancialInstrument, RateHistory.instrument_id == FinancialInstrument.id)
        .where(
            FinancialInstrument.country == country,
            FinancialInstrument.asset_class == AssetClass.GOLD,
            RateHistory.value_type == "spot_price",
            RateHistory.recorded_at >= since,
        )
        .group_by(bucket)
        .order_by(bucket)
    ).all()

    spot = [
        TrendPoint(value=float(row.spot), recorded_at=row.bucket)
        for row in rows
        if row.spot is not None
    ]
    return GoldTrendSeries(spot=spot)


def get_market_trends_history(
    db: Session,
    country: CountryCode,
    days: int = 7,
) -> MarketTrendsHistoryResponse:
    since = datetime.now(UTC) - timedelta(days=days)

    deposits = _aggregate_yield_series(
        db,
        country=country,
        asset_class=AssetClass.BANK_DEPOSIT,
        value_type="rate",
        since=since,
        days=days,
    )
    bonds = _aggregate_yield_series(
        db,
        country=country,
        asset_class=AssetClass.GOVERNMENT_BOND,
        value_type="yield",
        since=since,
        days=days,
    )
    gold = _gold_spot_series(db, country=country, since=since, days=days)

    return MarketTrendsHistoryResponse(
        period_days=days,
        deposits=deposits,
        bonds=bonds,
        gold=gold,
    )
