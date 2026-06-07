import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pribilka.db.base import Base
from pribilka.models.enums import CurrencyCode


class FxRate(Base):
    __tablename__ = "fx_rates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_instruments.id"), unique=True, nullable=False
    )
    base_currency: Mapped[CurrencyCode] = mapped_column(Enum(CurrencyCode), nullable=False)
    quote_currency: Mapped[CurrencyCode] = mapped_column(Enum(CurrencyCode), nullable=False)
    bid_price: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    ask_price: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    mid_market_rate: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, index=True)
    daily_change_percent: Mapped[float | None] = mapped_column(Numeric(6, 3))
    weekly_change_percent: Mapped[float | None] = mapped_column(Numeric(6, 3))
    monthly_change_percent: Mapped[float | None] = mapped_column(Numeric(6, 3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    instrument: Mapped["FinancialInstrument"] = relationship(back_populates="fx_rate")
