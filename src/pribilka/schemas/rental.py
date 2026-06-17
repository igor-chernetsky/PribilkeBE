from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from pribilka.models.enums import RentalListingType


class RentalCityResponse(BaseModel):
    slug: str
    name_pl: str
    name_en: str


class RentalDistributionResponse(BaseModel):
    sample_size: int
    p25: float | None = None
    median: float | None = None
    p75: float | None = None


class RentalMarketSegmentResponse(BaseModel):
    city_slug: str
    listing_type: RentalListingType
    room_count: int
    period_start: datetime
    prices: RentalDistributionResponse
    price_per_sqm: RentalDistributionResponse


class RentalYieldSegmentResponse(BaseModel):
    city_slug: str
    room_count: int
    period_start: datetime
    sale_sample_size: int
    rent_sample_size: int
    sale_price_median: float | None = None
    rent_price_median: float | None = None
    gross_yield: RentalDistributionResponse


class RentalMarketOverviewResponse(BaseModel):
    cities: list[RentalCityResponse]
    segments: list[RentalMarketSegmentResponse]
    yields: list[RentalYieldSegmentResponse]
    updated_at: datetime | None = None


class RentalTrendPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start: datetime
    p25: float | None = None
    median: float | None = None
    p75: float | None = None
    sample_size: int = 0


class RentalPriceTrendSeries(BaseModel):
    city_slug: str
    room_count: int
    listing_type: RentalListingType
    points: list[RentalTrendPoint]


class RentalYieldTrendSeries(BaseModel):
    city_slug: str
    room_count: int
    points: list[RentalTrendPoint]


class RentalMarketHistoryResponse(BaseModel):
    days: int = Field(ge=1, le=180)
    sale_prices: list[RentalPriceTrendSeries]
    rent_prices: list[RentalPriceTrendSeries]
    gross_yields: list[RentalYieldTrendSeries]
