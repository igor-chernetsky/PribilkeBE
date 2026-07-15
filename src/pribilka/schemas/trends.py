from datetime import datetime

from pydantic import BaseModel


class TrendPoint(BaseModel):
    value: float
    recorded_at: datetime


class YieldTrendSeries(BaseModel):
    best: list[TrendPoint]
    average: list[TrendPoint]


class GoldTrendSeries(BaseModel):
    spot: list[TrendPoint]


class FxTrendSeries(BaseModel):
    usd_pln: list[TrendPoint]
    eur_pln: list[TrendPoint]


class MarketTrendsHistoryResponse(BaseModel):
    period_days: int
    deposits: YieldTrendSeries
    bonds: YieldTrendSeries
    gold: GoldTrendSeries
    fx: FxTrendSeries = FxTrendSeries(usd_pln=[], eur_pln=[])
