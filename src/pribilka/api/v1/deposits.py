from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from pribilka.db.session import get_db
from pribilka.models.enums import CountryCode, CurrencyCode
from pribilka.schemas.common import DepositResponse, PaginatedResponse
from pribilka.services import market_data

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_deposits(
    country: CountryCode | None = None,
    currency: CurrencyCode | None = None,
    min_rate: float | None = Query(None, ge=0),
    max_term_months: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total = market_data.list_deposits(
        db,
        country=country,
        currency=currency,
        min_rate=min_rate,
        max_term_months=max_term_months,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/{deposit_id}", response_model=DepositResponse)
def get_deposit(deposit_id: UUID, db: Session = Depends(get_db)):
    deposit = market_data.get_deposit(db, deposit_id)
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return deposit
