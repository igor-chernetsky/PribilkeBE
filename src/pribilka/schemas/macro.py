from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from pribilka.models.enums import CountryCode, MacroIndicatorKind


class MacroPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: MacroIndicatorKind
    value: float
    as_of_date: date
    source_name: str | None = None


class MacroSeries(BaseModel):
    kind: MacroIndicatorKind
    points: list[MacroPoint]


class MacroSummaryResponse(BaseModel):
    country: CountryCode
    nbp_reference_rate: float | None = None
    nbp_reference_as_of: date | None = None
    cpi_yoy: float | None = None
    cpi_as_of: date | None = None
    best_deposit_rate: float | None = None
    real_deposit_rate: float | None = None
    deposit_vs_nbp_pp: float | None = None
    series: list[MacroSeries] = []


class MacroHistoryResponse(BaseModel):
    country: CountryCode
    series: list[MacroSeries]
