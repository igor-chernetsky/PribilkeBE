import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pribilka.db.base import Base
from pribilka.models.enums import RentalListingType


class RentalListing(Base):
    """Fresh property listing snapshot from an external portal (Otodom, etc.)."""

    __tablename__ = "rental_listings"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_rental_listings_source_external"),
        Index("ix_rental_listings_fresh_lookup", "city_slug", "listing_type", "room_count", "last_seen_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="otodom")
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    listing_type: Mapped[RentalListingType] = mapped_column(
        Enum(RentalListingType, native_enum=False, length=16),
        nullable=False,
    )
    city_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    room_count: Mapped[int] = mapped_column(Integer, nullable=False)
    price_pln: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    area_sqm: Mapped[float | None] = mapped_column(Numeric(8, 2))
    price_per_sqm: Mapped[float | None] = mapped_column(Numeric(10, 2))
    title: Mapped[str | None] = mapped_column(String(512))
    url: Mapped[str | None] = mapped_column(String(1024))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
