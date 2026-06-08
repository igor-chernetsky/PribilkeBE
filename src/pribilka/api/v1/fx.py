from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from pribilka.api.deps import parse_market_country
from pribilka.db.session import get_db
from pribilka.models.enums import CountryCode, CurrencyCode
from pribilka.models.rate_history import RateHistory
from pribilka.schemas.common import FxResponse
from pribilka.services import market_data

router = APIRouter()


@router.get("", response_model=list[FxResponse])
def list_fx(
    country: CountryCode = Depends(parse_market_country),
    db: Session = Depends(get_db),
):
    return market_data.list_fx_rates(db, country)


@router.get("/history")
def get_fx_history(
    base: CurrencyCode,
    country: CountryCode = Depends(parse_market_country),
    quote: CurrencyCode = CurrencyCode.PLN,
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    rates = market_data.list_fx_rates(db, country)
    match = next(
        (r for r in rates if r.base_currency == base and r.quote_currency == quote),
        None,
    )
    if not match:
        raise HTTPException(status_code=404, detail="FX pair not found")

    history = db.scalars(
        select(RateHistory)
        .where(
            RateHistory.instrument_id == match.instrument_id,
            RateHistory.value_type == "mid_rate",
        )
        .order_by(desc(RateHistory.recorded_at))
        .limit(limit)
    ).all()

    return [
        {"value": float(h.value), "recorded_at": h.recorded_at.isoformat()} for h in history
    ]
