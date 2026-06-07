import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pribilka.db.base import Base


class GoldPrice(Base):
    __tablename__ = "gold_prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_instruments.id"), unique=True, nullable=False
    )
    spot_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    buy_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    sell_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    daily_change_percent: Mapped[float | None] = mapped_column(Numeric(6, 3))
    weekly_change_percent: Mapped[float | None] = mapped_column(Numeric(6, 3))
    monthly_change_percent: Mapped[float | None] = mapped_column(Numeric(6, 3))
    annual_change_percent: Mapped[float | None] = mapped_column(Numeric(6, 3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    instrument: Mapped["FinancialInstrument"] = relationship(back_populates="gold_price")
