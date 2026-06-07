import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pribilka.db.base import Base
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode, RiskLevel


class FinancialInstrument(Base):
    __tablename__ = "financial_instruments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_class: Mapped[AssetClass] = mapped_column(Enum(AssetClass), nullable=False, index=True)
    country: Mapped[CountryCode] = mapped_column(Enum(CountryCode), nullable=False, index=True)
    currency: Mapped[CurrencyCode] = mapped_column(Enum(CurrencyCode), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    source_name: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    opportunity_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.LOW)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    deposit: Mapped["BankDeposit | None"] = relationship(back_populates="instrument", uselist=False)
    bond: Mapped["Bond | None"] = relationship(back_populates="instrument", uselist=False)
    gold_price: Mapped["GoldPrice | None"] = relationship(back_populates="instrument", uselist=False)
    fx_rate: Mapped["FxRate | None"] = relationship(back_populates="instrument", uselist=False)
    rate_history: Mapped[list["RateHistory"]] = relationship(back_populates="instrument")
    market_events: Mapped[list["MarketEvent"]] = relationship(back_populates="instrument")
