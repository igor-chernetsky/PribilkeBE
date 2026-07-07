from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DigestSection(BaseModel):
    heading: str
    body: str


class DigestHighlights(BaseModel):
    best_deposit_rate: float | None = None
    best_bond_yield: float | None = None
    gold_change_percent: float | None = None
    rental_leader_city: str | None = None
    rental_leader_yield: float | None = None


class WeeklyDigestContent(BaseModel):
    title: str
    summary: str
    sections: list[DigestSection] = Field(default_factory=list)
    highlights: DigestHighlights | None = None


class WeeklyDigestSummaryResponse(BaseModel):
    id: UUID
    week_start: date
    week_end: date


class WeeklyDigestResponse(BaseModel):
    id: UUID
    country: str
    week_start: date
    week_end: date
    locale: str
    title: str
    summary: str
    sections: list[DigestSection]
    highlights: DigestHighlights | None = None
    source: str
    generated_at: datetime
