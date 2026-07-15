from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from pribilka.models.bank_deposit import BankDeposit
from pribilka.models.enums import CountryCode, MacroIndicatorKind
from pribilka.models.financial_instrument import FinancialInstrument
from pribilka.models.macro_indicator import MacroIndicator
from pribilka.schemas.macro import MacroHistoryResponse, MacroPoint, MacroSeries, MacroSummaryResponse


def _latest(
    db: Session,
    *,
    country: CountryCode,
    kind: MacroIndicatorKind,
) -> MacroIndicator | None:
    return db.scalar(
        select(MacroIndicator)
        .where(MacroIndicator.country == country, MacroIndicator.kind == kind)
        .order_by(desc(MacroIndicator.as_of_date))
        .limit(1)
    )


def _history(
    db: Session,
    *,
    country: CountryCode,
    kind: MacroIndicatorKind,
    since: date,
) -> list[MacroPoint]:
    rows = db.scalars(
        select(MacroIndicator)
        .where(
            MacroIndicator.country == country,
            MacroIndicator.kind == kind,
            MacroIndicator.as_of_date >= since,
        )
        .order_by(MacroIndicator.as_of_date)
    ).all()
    return [
        MacroPoint(
            kind=row.kind,
            value=float(row.value),
            as_of_date=row.as_of_date,
            source_name=row.source_name,
        )
        for row in rows
    ]


def _best_deposit_rate(db: Session, country: CountryCode) -> float | None:
    value = db.scalar(
        select(func.max(BankDeposit.annual_interest_rate))
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.country == country,
            FinancialInstrument.is_active.is_(True),
        )
    )
    return float(value) if value is not None else None


def get_latest_macro_fields(db: Session, country: CountryCode) -> dict:
    """Compact fields for market summary — avoids circular service imports."""
    nbp = _latest(db, country=country, kind=MacroIndicatorKind.NBP_REFERENCE_RATE)
    cpi = _latest(db, country=country, kind=MacroIndicatorKind.CPI_YOY)
    best_deposit = _best_deposit_rate(db, country)
    nbp_value = float(nbp.value) if nbp else None
    cpi_value = float(cpi.value) if cpi else None
    real_deposit = None
    if best_deposit is not None and cpi_value is not None:
        real_deposit = round(best_deposit - cpi_value, 3)
    return {
        "nbp_reference_rate": nbp_value,
        "nbp_reference_as_of": nbp.as_of_date if nbp else None,
        "cpi_yoy": cpi_value,
        "cpi_as_of": cpi.as_of_date if cpi else None,
        "real_deposit_rate": real_deposit,
    }


def get_macro_summary(
    db: Session,
    country: CountryCode,
    *,
    history_months: int = 36,
) -> MacroSummaryResponse:
    nbp = _latest(db, country=country, kind=MacroIndicatorKind.NBP_REFERENCE_RATE)
    cpi = _latest(db, country=country, kind=MacroIndicatorKind.CPI_YOY)
    best_deposit = _best_deposit_rate(db, country)

    cpi_value = float(cpi.value) if cpi else None
    nbp_value = float(nbp.value) if nbp else None

    real_deposit = None
    if best_deposit is not None and cpi_value is not None:
        real_deposit = round(best_deposit - cpi_value, 3)

    deposit_vs_nbp = None
    if best_deposit is not None and nbp_value is not None:
        deposit_vs_nbp = round(best_deposit - nbp_value, 3)

    since = date.today() - timedelta(days=max(history_months, 1) * 31)
    series = [
        MacroSeries(
            kind=MacroIndicatorKind.NBP_REFERENCE_RATE,
            points=_history(
                db,
                country=country,
                kind=MacroIndicatorKind.NBP_REFERENCE_RATE,
                since=since,
            ),
        ),
        MacroSeries(
            kind=MacroIndicatorKind.CPI_YOY,
            points=_history(
                db,
                country=country,
                kind=MacroIndicatorKind.CPI_YOY,
                since=since,
            ),
        ),
    ]

    return MacroSummaryResponse(
        country=country,
        nbp_reference_rate=nbp_value,
        nbp_reference_as_of=nbp.as_of_date if nbp else None,
        cpi_yoy=cpi_value,
        cpi_as_of=cpi.as_of_date if cpi else None,
        best_deposit_rate=best_deposit,
        real_deposit_rate=real_deposit,
        deposit_vs_nbp_pp=deposit_vs_nbp,
        series=series,
    )


def get_macro_history(
    db: Session,
    country: CountryCode,
    *,
    months: int = 36,
) -> MacroHistoryResponse:
    since = date.today() - timedelta(days=max(months, 1) * 31)
    series = [
        MacroSeries(
            kind=kind,
            points=_history(db, country=country, kind=kind, since=since),
        )
        for kind in (
            MacroIndicatorKind.NBP_REFERENCE_RATE,
            MacroIndicatorKind.CPI_YOY,
        )
    ]
    return MacroHistoryResponse(country=country, series=series)
