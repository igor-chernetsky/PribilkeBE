from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pribilka.api.deps import MarketCountry
from pribilka.db.session import get_db
from pribilka.schemas.macro import MacroHistoryResponse, MacroSummaryResponse
from pribilka.services import macro_data

router = APIRouter()


@router.get("", response_model=MacroSummaryResponse)
def get_macro_summary(
    country: MarketCountry,
    db: Session = Depends(get_db),
    history_months: int = Query(36, ge=6, le=120),
) -> MacroSummaryResponse:
    return macro_data.get_macro_summary(db, country, history_months=history_months)


@router.get("/history", response_model=MacroHistoryResponse)
def get_macro_history(
    country: MarketCountry,
    db: Session = Depends(get_db),
    months: int = Query(36, ge=6, le=120),
) -> MacroHistoryResponse:
    return macro_data.get_macro_history(db, country, months=months)
