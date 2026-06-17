from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median


@dataclass(frozen=True)
class DistributionStats:
    sample_size: int
    p25: float | None
    median: float | None
    p75: float | None


@dataclass(frozen=True)
class YieldStats:
    sale_sample_size: int
    rent_sample_size: int
    sale_price_median: float | None
    rent_price_median: float | None
    gross_yield_p25: float | None
    gross_yield_median: float | None
    gross_yield_p75: float | None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]

    ordered = sorted(values)
    rank = (len(ordered) - 1) * (p / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def distribution_stats(values: list[float]) -> DistributionStats:
    cleaned = [float(v) for v in values if v is not None and v > 0]
    if not cleaned:
        return DistributionStats(sample_size=0, p25=None, median=None, p75=None)
    return DistributionStats(
        sample_size=len(cleaned),
        p25=percentile(cleaned, 25),
        median=median(cleaned),
        p75=percentile(cleaned, 75),
    )


def gross_annual_yield_percent(monthly_rent: float, sale_price: float) -> float | None:
    if monthly_rent <= 0 or sale_price <= 0:
        return None
    return round((monthly_rent * 12 / sale_price) * 100, 3)


def yield_stats(
    sale_prices: list[float],
    rent_prices: list[float],
) -> YieldStats:
    sale = distribution_stats(sale_prices)
    rent = distribution_stats(rent_prices)

    conservative = None
    base = None
    optimistic = None

    if sale.p75 and rent.p25:
        conservative = gross_annual_yield_percent(rent.p25, sale.p75)
    if sale.median and rent.median:
        base = gross_annual_yield_percent(rent.median, sale.median)
    if sale.p25 and rent.p75:
        optimistic = gross_annual_yield_percent(rent.p75, sale.p25)

    return YieldStats(
        sale_sample_size=sale.sample_size,
        rent_sample_size=rent.sample_size,
        sale_price_median=sale.median,
        rent_price_median=rent.median,
        gross_yield_p25=conservative,
        gross_yield_median=base,
        gross_yield_p75=optimistic,
    )


def truncate_to_12h_period(moment: datetime) -> datetime:
    moment = moment.astimezone(UTC)
    hour_bucket = (moment.hour // 12) * 12
    return moment.replace(hour=hour_bucket, minute=0, second=0, microsecond=0)


def fresh_cutoff(now: datetime, *, max_age_hours: int = 48) -> datetime:
    return now - timedelta(hours=max_age_hours)
