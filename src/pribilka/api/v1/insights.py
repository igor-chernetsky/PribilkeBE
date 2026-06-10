from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pribilka.api.deps import parse_market_country
from pribilka.db.session import get_db
from pribilka.models.enums import CountryCode
from pribilka.schemas.insights import InsightResponse
from pribilka.services.ai_insights import get_bond_insight, get_deposit_insight

router = APIRouter()


@router.get("/deposits/{deposit_id}", response_model=InsightResponse)
def deposit_insight(
    deposit_id: UUID,
    country: CountryCode = Depends(parse_market_country),
    db: Session = Depends(get_db),
):
    insight = get_deposit_insight(db, deposit_id, country)
    if not insight:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return insight


@router.get("/bonds/{bond_id}", response_model=InsightResponse)
def bond_insight(
    bond_id: UUID,
    country: CountryCode = Depends(parse_market_country),
    db: Session = Depends(get_db),
):
    insight = get_bond_insight(db, bond_id, country)
    if not insight:
        raise HTTPException(status_code=404, detail="Bond not found")
    return insight
