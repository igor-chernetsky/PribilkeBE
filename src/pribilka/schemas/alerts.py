from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode, RiskLevel
from pribilka.schemas.common import BaseSchema


class AlertCreate(BaseModel):
    name: str
    country: CountryCode | None = CountryCode.PL
    currency: CurrencyCode | None = CurrencyCode.PLN
    asset_class: AssetClass | None = None
    minimum_yield: float | None = Field(None, ge=0, le=100)
    maximum_term_months: int | None = Field(None, ge=1)
    minimum_opportunity_score: float | None = Field(None, ge=0, le=100)
    risk_level: RiskLevel | None = None


class AlertUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    country: CountryCode | None = None
    currency: CurrencyCode | None = None
    asset_class: AssetClass | None = None
    minimum_yield: float | None = Field(None, ge=0, le=100)
    maximum_term_months: int | None = Field(None, ge=1)
    minimum_opportunity_score: float | None = Field(None, ge=0, le=100)
    risk_level: RiskLevel | None = None


class AlertResponse(BaseSchema):
    id: UUID
    user_id: str
    name: str
    is_active: bool
    country: CountryCode | None
    currency: CurrencyCode | None
    asset_class: AssetClass | None
    minimum_yield: float | None
    maximum_term_months: int | None
    minimum_opportunity_score: float | None
    risk_level: RiskLevel | None
    created_at: datetime
    updated_at: datetime


class NotificationResponse(BaseSchema):
    id: UUID
    user_id: str
    alert_id: UUID | None
    instrument_id: UUID | None
    group_id: UUID | None = None
    match_count: int | None = None
    title: str
    message: str
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class MarkNotificationsReadRequest(BaseModel):
    notification_ids: list[UUID]
