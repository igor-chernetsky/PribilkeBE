import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from pribilka.db.base import Base
from pribilka.models.enums import CountryCode


class WeeklyDigest(Base):
    __tablename__ = "weekly_digests"
    __table_args__ = (UniqueConstraint("country", "week_start", name="uq_weekly_digest_country_week"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country: Mapped[CountryCode] = mapped_column(Enum(CountryCode), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    content_en: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_pl: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="template")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
