import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pribilka.db.base import Base


class RateHistory(Base):
    __tablename__ = "rate_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_instruments.id"), nullable=False, index=True
    )
    value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    value_type: Mapped[str] = mapped_column(String(50), default="rate")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    instrument: Mapped["FinancialInstrument"] = relationship(back_populates="rate_history")
