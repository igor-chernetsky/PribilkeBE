from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pribilka.api.deps import parse_market_country
from pribilka.db.session import get_db
from pribilka.models.enums import CountryCode
from pribilka.schemas.rental import RentalMarketHistoryResponse, RentalMarketOverviewResponse
from pribilka.services.rental_market import get_latest_rental_overview, get_rental_market_history, list_rental_cities

router = APIRouter()


@router.get("/cities")
def rental_cities(country: CountryCode = Depends(parse_market_country)):
    if country != CountryCode.PL:
        return []
    return list_rental_cities()


@router.get("/overview", response_model=RentalMarketOverviewResponse)
def rental_overview(
    country: CountryCode = Depends(parse_market_country),
    db: Session = Depends(get_db),
):
    if country != CountryCode.PL:
        return RentalMarketOverviewResponse(cities=[], segments=[], yields=[], updated_at=None)
    return get_latest_rental_overview(db)


@router.get("/history", response_model=RentalMarketHistoryResponse)
def rental_history(
    country: CountryCode = Depends(parse_market_country),
    days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_db),
):
    if country != CountryCode.PL:
        return RentalMarketHistoryResponse(days=days, sale_prices=[], rent_prices=[], gross_yields=[])
    return get_rental_market_history(db, days=days)
