import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pribilka.db.base import Base


class RentalYieldSnapshot(Base):
    """Estimated gross rental yield range for buy-to-let (sale vs rent medians)."""

    __tablename__ = "rental_yield_snapshots"
    __table_args__ = (
        UniqueConstraint("city_slug", "room_count", "period_start", name="uq_rental_yield_snapshot_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    room_count: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sale_sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rent_sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sale_price_median: Mapped[float | None] = mapped_column(Numeric(12, 2))
    rent_price_median: Mapped[float | None] = mapped_column(Numeric(12, 2))
    gross_yield_p25: Mapped[float | None] = mapped_column(Numeric(6, 3))
    gross_yield_median: Mapped[float | None] = mapped_column(Numeric(6, 3))
    gross_yield_p75: Mapped[float | None] = mapped_column(Numeric(6, 3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
