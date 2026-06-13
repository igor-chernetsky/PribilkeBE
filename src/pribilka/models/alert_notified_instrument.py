import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pribilka.db.base import Base


class AlertNotifiedInstrument(Base):
    """Tracks last notified snapshot for an instrument under an alert."""

    __tablename__ = "alert_notified_instruments"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_alerts.id"), primary_key=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    last_notified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_notified_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_notified_rank: Mapped[float | None] = mapped_column(Float, nullable=True)
