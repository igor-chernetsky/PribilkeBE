import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pribilka.db.base import Base


class Bond(Base):
    __tablename__ = "bonds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_instruments.id"), unique=True, nullable=False
    )
    is_government: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    bond_series: Mapped[str | None] = mapped_column(String(100))
    industry_sector: Mapped[str | None] = mapped_column(String(100))
    credit_rating: Mapped[str | None] = mapped_column(String(20))
    isin: Mapped[str | None] = mapped_column(String(12), index=True)
    issue_date: Mapped[date | None] = mapped_column(Date)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    coupon_rate: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    yield_to_maturity: Mapped[float | None] = mapped_column(Numeric(6, 3), index=True)
    market_price: Mapped[float | None] = mapped_column(Numeric(10, 4))
    face_value: Mapped[float] = mapped_column(Numeric(10, 2), default=100)
    minimum_investment: Mapped[float | None] = mapped_column(Numeric(14, 2))
    trading_volume: Mapped[float | None] = mapped_column(Numeric(18, 2))
    liquidity_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    instrument: Mapped["FinancialInstrument"] = relationship(back_populates="bond")
