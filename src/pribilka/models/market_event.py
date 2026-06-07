import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pribilka.db.base import Base
from pribilka.models.enums import MarketEventType


class MarketEvent(Base):
    __tablename__ = "market_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_instruments.id"), nullable=False, index=True
    )
    event_type: Mapped[MarketEventType] = mapped_column(Enum(MarketEventType), nullable=False)
    previous_value: Mapped[float | None] = mapped_column(Numeric(12, 4))
    new_value: Mapped[float | None] = mapped_column(Numeric(12, 4))
    description: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    instrument: Mapped["FinancialInstrument"] = relationship(back_populates="market_events")
