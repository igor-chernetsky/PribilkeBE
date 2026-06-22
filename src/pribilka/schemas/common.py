from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from pribilka.models.enums import (
    AssetClass,
    CountryCode,
    CurrencyCode,
    InterestCapitalization,
    RiskLevel,
)


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


class InstrumentBase(BaseSchema):
    id: UUID
    asset_class: AssetClass
    country: CountryCode
    currency: CurrencyCode
    source_name: str
    source_url: str
    opportunity_score: float | None
    risk_level: RiskLevel
    last_collected_at: datetime | None


class DepositResponse(BaseSchema):
    id: UUID
    instrument_id: UUID
    institution_name: str
    bank_slug: str | None = None
    product_name: str
    annual_interest_rate: float
    term_months: int
    interest_capitalization: InterestCapitalization
    minimum_deposit_amount: float | None
    maximum_deposit_amount: float | None
    early_withdrawal_conditions: str | None
    promotional_rate_requirements: str | None
    country: CountryCode
    currency: CurrencyCode
    opportunity_score: float | None
    risk_level: RiskLevel
    last_collected_at: datetime | None


class BondResponse(BaseSchema):
    id: UUID
    instrument_id: UUID
    is_government: bool
    issuer: str
    bond_series: str | None
    isin: str | None
    maturity_date: datetime
    coupon_rate: float
    yield_to_maturity: float | None
    market_price: float | None
    country: CountryCode
    currency: CurrencyCode
    opportunity_score: float | None
    risk_level: RiskLevel
    last_collected_at: datetime | None


class GoldResponse(BaseSchema):
    id: UUID
    instrument_id: UUID
    spot_price: float
    buy_price: float | None
    sell_price: float | None
    daily_change_percent: float | None
    weekly_change_percent: float | None
    monthly_change_percent: float | None
    annual_change_percent: float | None
    currency: CurrencyCode
    risk_level: RiskLevel
    last_collected_at: datetime | None


class FxResponse(BaseSchema):
    id: UUID
    instrument_id: UUID
    base_currency: CurrencyCode
    quote_currency: CurrencyCode
    bid_price: float
    ask_price: float
    mid_market_rate: float
    daily_change_percent: float | None
    weekly_change_percent: float | None
    monthly_change_percent: float | None
    source_name: str
    risk_level: RiskLevel
    last_collected_at: datetime | None


class DigestTeaserResponse(BaseSchema):
    available: bool = False
    week_start: date | None = None
    title_pl: str | None = None
    title_en: str | None = None
    summary_pl: str | None = None
    summary_en: str | None = None
    highlight_pl: str | None = None
    highlight_en: str | None = None


class MarketSummaryResponse(BaseSchema):
    country: CountryCode
    deposits_count: int
    bonds_count: int
    best_deposit_rate: float | None
    best_bond_yield: float | None
    avg_deposit_yield: float | None = None
    avg_bond_yield: float | None = None
    gold_spot_price: float | None
    gold_daily_change_percent: float | None = None
    usd_pln_rate: float | None
    eur_pln_rate: float | None
    best_rental_yield: float | None = None
    best_rental_yield_city_slug: str | None = None
    best_rental_yield_city_name_pl: str | None = None
    best_rental_yield_city_name_en: str | None = None
    rental_yield_room_count: int | None = None
    rental_yield_updated_at: datetime | None = None
    digest_teaser: DigestTeaserResponse | None = None
    updated_at: datetime | None
