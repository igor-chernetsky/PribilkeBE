from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
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


@dataclass(frozen=True)
class _RateEvent:
    instrument_id: uuid.UUID
    recorded_at: datetime
    value: float


def _truncate_to_bucket(moment: datetime, *, hourly: bool) -> datetime:
    moment = moment.astimezone(UTC)
    if hourly:
        return moment.replace(minute=0, second=0, microsecond=0)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _bucket_delta(*, hourly: bool) -> timedelta:
    return timedelta(hours=1) if hourly else timedelta(days=1)


def _iter_bucket_starts(since: datetime, now: datetime, *, hourly: bool) -> list[datetime]:
    start = _truncate_to_bucket(since, hourly=hourly)
    end = _truncate_to_bucket(now, hourly=hourly)
    step = _bucket_delta(hourly=hourly)
    buckets: list[datetime] = []
    current = start
    while current <= end:
        buckets.append(current)
        current += step
    return buckets


def _build_carry_forward_series(
    events: list[_RateEvent],
    buckets: list[datetime],
    *,
    hourly: bool,
) -> YieldTrendSeries:
    """Market best/avg at each bucket using last-known rate per instrument."""
    if not buckets:
        return YieldTrendSeries(best=[], average=[])

    events_sorted = sorted(events, key=lambda event: (event.recorded_at, str(event.instrument_id)))
    step = _bucket_delta(hourly=hourly)
    active: dict[uuid.UUID, float] = {}
    index = 0
    best: list[TrendPoint] = []
    average: list[TrendPoint] = []

    for bucket_start in buckets:
        bucket_end = bucket_start + step
        while index < len(events_sorted) and events_sorted[index].recorded_at < bucket_end:
            event = events_sorted[index]
            active[event.instrument_id] = event.value
            index += 1
        if not active:
            continue
        values = list(active.values())
        best.append(TrendPoint(value=max(values), recorded_at=bucket_start))
        average.append(TrendPoint(value=sum(values) / len(values), recorded_at=bucket_start))

    return YieldTrendSeries(best=best, average=average)


def _fetch_rate_events(
    db: Session,
    *,
    country: CountryCode,
    asset_class: AssetClass,
    value_type: str,
) -> list[_RateEvent]:
    rows = db.execute(
        select(
            RateHistory.instrument_id,
            RateHistory.recorded_at,
            RateHistory.value,
        )
        .join(FinancialInstrument, RateHistory.instrument_id == FinancialInstrument.id)
        .where(
            FinancialInstrument.country == country,
            FinancialInstrument.asset_class == asset_class,
            FinancialInstrument.is_active.is_(True),
            RateHistory.value_type == value_type,
        )
        .order_by(RateHistory.recorded_at)
    ).all()
    return [
        _RateEvent(
            instrument_id=row.instrument_id,
            recorded_at=row.recorded_at,
            value=float(row.value),
        )
        for row in rows
    ]


def _carry_forward_yield_series(
    db: Session,
    *,
    country: CountryCode,
    asset_class: AssetClass,
    value_type: str,
    since: datetime,
    days: int,
) -> YieldTrendSeries:
    hourly = days <= 7
    now = datetime.now(UTC)
    buckets = _iter_bucket_starts(since, now, hourly=hourly)
    events = _fetch_rate_events(
        db,
        country=country,
        asset_class=asset_class,
        value_type=value_type,
    )
    return _build_carry_forward_series(events, buckets, hourly=hourly)


def _gold_spot_series(
    db: Session,
    *,
    country: CountryCode,
    since: datetime,
    days: int,
) -> GoldTrendSeries:
    from sqlalchemy import func

    bucket = func.date_trunc("hour" if days <= 7 else "day", RateHistory.recorded_at).label("bucket")

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

    deposits = _carry_forward_yield_series(
        db,
        country=country,
        asset_class=AssetClass.BANK_DEPOSIT,
        value_type="rate",
        since=since,
        days=days,
    )
    bonds = _carry_forward_yield_series(
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
