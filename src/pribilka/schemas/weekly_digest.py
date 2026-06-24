from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DigestSection(BaseModel):
    heading: str
    body: str


class WeeklyDigestContent(BaseModel):
    title: str
    summary: str
    sections: list[DigestSection] = Field(default_factory=list)


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
    source: str
    generated_at: datetime
