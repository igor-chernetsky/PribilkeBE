from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.api.deps import parse_market_country
from pribilka.db.session import get_db
from pribilka.models.enums import CountryCode
from pribilka.models.weekly_digest import WeeklyDigest
from pribilka.schemas.weekly_digest import (
    WeeklyDigestResponse,
    WeeklyDigestSummaryResponse,
)
from pribilka.services.weekly_digest import pick_digest_content

router = APIRouter()


def _to_response(digest: WeeklyDigest, locale: str) -> WeeklyDigestResponse:
    content = pick_digest_content(digest, locale)
    return WeeklyDigestResponse(
        id=digest.id,
        country=digest.country.value,
        week_start=digest.week_start,
        week_end=digest.week_end,
        locale=locale if locale.lower().startswith("pl") else "en",
        title=content.title,
        summary=content.summary,
        sections=content.sections,
        highlights=content.highlights,
        source=digest.source,
        generated_at=digest.created_at,
    )


@router.get("/archive", response_model=list[WeeklyDigestSummaryResponse])
def list_weekly_digests(
    country: CountryCode = Depends(parse_market_country),
    limit: int = Query(12, ge=1, le=52),
    db: Session = Depends(get_db),
):
    digests = db.scalars(
        select(WeeklyDigest)
        .where(WeeklyDigest.country == country)
        .order_by(WeeklyDigest.week_start.desc())
        .limit(limit)
    ).all()
    return [
        WeeklyDigestSummaryResponse(
            id=digest.id,
            week_start=digest.week_start,
            week_end=digest.week_end,
        )
        for digest in digests
    ]


@router.get("/latest", response_model=WeeklyDigestResponse)
def latest_weekly_digest(
    country: CountryCode = Depends(parse_market_country),
    locale: str = Query("en", pattern="^(en|pl)$"),
    db: Session = Depends(get_db),
):
    digest = db.scalar(
        select(WeeklyDigest)
        .where(WeeklyDigest.country == country)
        .order_by(WeeklyDigest.week_start.desc())
        .limit(1)
    )
    if not digest:
        raise HTTPException(status_code=404, detail="Weekly digest not available yet")
    return _to_response(digest, locale)


@router.get("/{digest_id}", response_model=WeeklyDigestResponse)
def get_weekly_digest(
    digest_id: UUID,
    locale: str = Query("en", pattern="^(en|pl)$"),
    db: Session = Depends(get_db),
):
    digest = db.get(WeeklyDigest, digest_id)
    if not digest:
        raise HTTPException(status_code=404, detail="Weekly digest not found")
    return _to_response(digest, locale)
