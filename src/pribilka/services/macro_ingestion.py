from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.models.enums import CountryCode, MacroIndicatorKind
from pribilka.models.macro_indicator import MacroIndicator


def ingest_macro_indicators(db: Session, records: list[dict]) -> int:
    if not records:
        return 0

    count = 0
    now = datetime.now(UTC)
    for record in records:
        kind = record["kind"]
        if isinstance(kind, str):
            kind = MacroIndicatorKind(kind)
        country = record.get("country", CountryCode.PL)
        if isinstance(country, str):
            country = CountryCode(country)
        as_of_date = record["as_of_date"]
        if isinstance(as_of_date, str):
            as_of_date = date.fromisoformat(as_of_date)

        existing = db.scalar(
            select(MacroIndicator).where(
                MacroIndicator.country == country,
                MacroIndicator.kind == kind,
                MacroIndicator.as_of_date == as_of_date,
            )
        )
        if existing is None:
            db.add(
                MacroIndicator(
                    country=country,
                    kind=kind,
                    value=record["value"],
                    as_of_date=as_of_date,
                    source_name=record.get("source_name", "macro"),
                    source_url=record.get("source_url"),
                )
            )
        else:
            existing.value = record["value"]
            existing.source_name = record.get("source_name", existing.source_name)
            existing.source_url = record.get("source_url", existing.source_url)
            existing.updated_at = now
        count += 1

    db.commit()
    return count
