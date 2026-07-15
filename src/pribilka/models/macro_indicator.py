import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pribilka.db.base import Base
from pribilka.models.enums import CountryCode, MacroIndicatorKind


class MacroIndicator(Base):
    __tablename__ = "macro_indicators"
    __table_args__ = (
        UniqueConstraint("country", "kind", "as_of_date", name="uq_macro_country_kind_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country: Mapped[CountryCode] = mapped_column(
        Enum(
            CountryCode,
            native_enum=False,
            length=16,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    kind: Mapped[MacroIndicatorKind] = mapped_column(
        Enum(
            MacroIndicatorKind,
            native_enum=False,
            length=32,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    value: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
