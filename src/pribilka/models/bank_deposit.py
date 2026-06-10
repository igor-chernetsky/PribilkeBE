import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pribilka.db.base import Base
from pribilka.models.enums import InterestCapitalization


class BankDeposit(Base):
    __tablename__ = "bank_deposits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_instruments.id"), unique=True, nullable=False
    )
    institution_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    bank_slug: Mapped[str | None] = mapped_column(String(64), index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    annual_interest_rate: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False, index=True)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    interest_capitalization: Mapped[InterestCapitalization] = mapped_column(
        Enum(InterestCapitalization), default=InterestCapitalization.AT_MATURITY
    )
    minimum_deposit_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    maximum_deposit_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    early_withdrawal_conditions: Mapped[str | None] = mapped_column(Text)
    promotional_rate_requirements: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    instrument: Mapped["FinancialInstrument"] = relationship(back_populates="deposit")
