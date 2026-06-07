from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from pribilka.db.session import get_db
from pribilka.models.enums import CountryCode
from pribilka.models.rate_history import RateHistory
from pribilka.schemas.common import GoldResponse
from pribilka.services import market_data

router = APIRouter()


@router.get("", response_model=GoldResponse)
def get_gold(country: CountryCode | None = None, db: Session = Depends(get_db)):
    gold = market_data.get_latest_gold(db, country)
    if not gold:
        raise HTTPException(status_code=404, detail="Gold price not available")
    return gold


@router.get("/history")
def get_gold_history(
    country: CountryCode | None = None,
    limit: int = 30,
    db: Session = Depends(get_db),
):
    gold = market_data.get_latest_gold(db, country)
    if not gold:
        raise HTTPException(status_code=404, detail="Gold price not available")

    history = db.scalars(
        select(RateHistory)
        .where(
            RateHistory.instrument_id == gold.instrument_id,
            RateHistory.value_type == "spot_price",
        )
        .order_by(desc(RateHistory.recorded_at))
        .limit(limit)
    ).all()

    return [
        {"value": float(h.value), "recorded_at": h.recorded_at.isoformat()} for h in history
    ]
