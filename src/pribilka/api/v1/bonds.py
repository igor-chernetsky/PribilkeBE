from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pribilka.db.session import get_db
from pribilka.models.enums import CountryCode
from pribilka.schemas.common import PaginatedResponse
from pribilka.services import market_data

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_bonds(
    country: CountryCode | None = None,
    government_only: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total = market_data.list_bonds(
        db,
        country=country,
        government_only=government_only,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)
