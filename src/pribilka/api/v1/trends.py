from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pribilka.api.deps import parse_market_country
from pribilka.db.session import get_db
from pribilka.models.enums import CountryCode
from pribilka.schemas.trends import MarketTrendsHistoryResponse
from pribilka.services.trends_history import get_market_trends_history

router = APIRouter()


@router.get("/history", response_model=MarketTrendsHistoryResponse)
def market_trends_history(
    country: CountryCode = Depends(parse_market_country),
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    return get_market_trends_history(db, country, days=days)
