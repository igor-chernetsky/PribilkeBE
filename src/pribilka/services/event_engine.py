from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from pribilka.models.enums import MarketEventType
from pribilka.models.market_event import MarketEvent


def detect_rate_change(
    db: Session,
    instrument_id,
    previous: Decimal | None,
    current: Decimal,
    value_label: str = "rate",
) -> MarketEvent | None:
    if previous is None:
        event = MarketEvent(
            instrument_id=instrument_id,
            event_type=MarketEventType.NEW_INSTRUMENT,
            new_value=float(current),
            description=f"New instrument with {value_label} {current}",
            occurred_at=datetime.now(UTC),
        )
        db.add(event)
        return event

    if current == previous:
        return None

    if current > previous:
        event_type = (
            MarketEventType.YIELD_INCREASED
            if value_label == "yield"
            else MarketEventType.RATE_INCREASED
        )
    else:
        event_type = (
            MarketEventType.YIELD_DECREASED
            if value_label == "yield"
            else MarketEventType.RATE_DECREASED
        )

    event = MarketEvent(
        instrument_id=instrument_id,
        event_type=event_type,
        previous_value=float(previous),
        new_value=float(current),
        description=f"{value_label} changed from {previous} to {current}",
        occurred_at=datetime.now(UTC),
    )
    db.add(event)
    return event
