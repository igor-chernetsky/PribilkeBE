from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pribilka.db.base import Base
from pribilka.models.bank_deposit import BankDeposit
from pribilka.models.enums import CountryCode, MacroIndicatorKind
from pribilka.models.financial_instrument import FinancialInstrument
from pribilka.models.macro_indicator import MacroIndicator
from pribilka.services.macro_data import get_macro_summary
from pribilka.services.macro_ingestion import ingest_macro_indicators

_TABLES = (
    FinancialInstrument.__table__,
    BankDeposit.__table__,
    MacroIndicator.__table__,
)


def _make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=list(_TABLES))
    return sessionmaker(bind=engine)()


def test_ingest_macro_indicators_upserts():
    db = _make_session()
    first = ingest_macro_indicators(
        db,
        [
            {
                "kind": MacroIndicatorKind.NBP_REFERENCE_RATE,
                "value": 5.25,
                "as_of_date": date(2025, 5, 8),
                "source_name": "nbp_interest_rates",
                "country": CountryCode.PL,
            }
        ],
    )
    second = ingest_macro_indicators(
        db,
        [
            {
                "kind": MacroIndicatorKind.NBP_REFERENCE_RATE,
                "value": 5.0,
                "as_of_date": date(2025, 5, 8),
                "source_name": "nbp_interest_rates",
                "country": CountryCode.PL,
            }
        ],
    )
    assert first == 1
    assert second == 1
    rows = db.scalars(select(MacroIndicator)).all()
    assert len(rows) == 1
    assert float(rows[0].value) == 5.0


def test_get_macro_summary_computes_spreads():
    db = _make_session()
    ingest_macro_indicators(
        db,
        [
            {
                "kind": MacroIndicatorKind.NBP_REFERENCE_RATE,
                "value": 5.25,
                "as_of_date": date(2025, 5, 8),
                "source_name": "nbp",
            },
            {
                "kind": MacroIndicatorKind.CPI_YOY,
                "value": 3.9,
                "as_of_date": date(2025, 3, 31),
                "source_name": "eurostat",
            },
        ],
    )
    summary = get_macro_summary(db, CountryCode.PL)
    assert summary.nbp_reference_rate == 5.25
    assert summary.cpi_yoy == 3.9
    assert summary.best_deposit_rate is None
    assert summary.real_deposit_rate is None
    assert len(summary.series) == 2
