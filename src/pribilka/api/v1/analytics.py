from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pribilka.db.session import get_db
from pribilka.models.enums import CountryCode, CurrencyCode
from pribilka.schemas.common import MarketSummaryResponse
from pribilka.services import market_data

router = APIRouter()


@router.get("/market-summary", response_model=MarketSummaryResponse)
def market_summary(country: CountryCode | None = None, db: Session = Depends(get_db)):
    return market_data.get_market_summary(db, country)


@router.get("/best-deposits")
def best_deposits(
    country: CountryCode | None = None,
    currency: CurrencyCode | None = CurrencyCode.PLN,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    items, _ = market_data.list_deposits(
        db, country=country, currency=currency, page=1, page_size=limit
    )
    return items


@router.get("/best-bonds")
def best_bonds(
    country: CountryCode | None = None,
    government_only: bool | None = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    items, _ = market_data.list_bonds(
        db, country=country, government_only=government_only, page=1, page_size=limit
    )
    return items


@router.get("/top-yields")
def top_yields(country: CountryCode | None = None, db: Session = Depends(get_db)):
    deposits, _ = market_data.list_deposits(db, country=country, page=1, page_size=5)
    bonds, _ = market_data.list_bonds(db, country=country, page=1, page_size=5)
    return {"deposits": deposits, "bonds": bonds}


@router.get("/market-opportunities")
def market_opportunities(country: CountryCode | None = None, db: Session = Depends(get_db)):
    summary = market_data.get_market_summary(db, country)
    deposits, _ = market_data.list_deposits(db, country=country, page=1, page_size=5)
    bonds, _ = market_data.list_bonds(db, country=country, page=1, page_size=5)
    return {
        "summary": summary,
        "top_deposits": deposits,
        "top_bonds": bonds,
    }
