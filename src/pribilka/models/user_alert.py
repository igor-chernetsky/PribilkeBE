import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pribilka.db.base import Base
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode, RiskLevel


class UserAlert(Base):
    __tablename__ = "user_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    country: Mapped[CountryCode | None] = mapped_column(Enum(CountryCode))
    currency: Mapped[CurrencyCode | None] = mapped_column(Enum(CurrencyCode))
    asset_class: Mapped[AssetClass | None] = mapped_column(Enum(AssetClass))
    minimum_yield: Mapped[float | None] = mapped_column(Numeric(6, 3))
    maximum_term_months: Mapped[int | None] = mapped_column(Integer)
    minimum_opportunity_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[RiskLevel | None] = mapped_column(Enum(RiskLevel))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    notifications: Mapped[list["Notification"]] = relationship(back_populates="alert")
