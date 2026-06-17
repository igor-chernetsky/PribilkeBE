import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pribilka.db.base import Base
from pribilka.models.enums import RentalListingType


class RentalMarketSnapshot(Base):
    """12-hour price/rent distribution for a city and apartment size."""

    __tablename__ = "rental_market_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "city_slug",
            "listing_type",
            "room_count",
            "period_start",
            name="uq_rental_market_snapshot_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_type: Mapped[RentalListingType] = mapped_column(Enum(RentalListingType), nullable=False)
    room_count: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_p25: Mapped[float | None] = mapped_column(Numeric(12, 2))
    price_median: Mapped[float | None] = mapped_column(Numeric(12, 2))
    price_p75: Mapped[float | None] = mapped_column(Numeric(12, 2))
    price_per_sqm_p25: Mapped[float | None] = mapped_column(Numeric(10, 2))
    price_per_sqm_median: Mapped[float | None] = mapped_column(Numeric(10, 2))
    price_per_sqm_p75: Mapped[float | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
