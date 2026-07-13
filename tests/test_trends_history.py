import uuid
from datetime import UTC, datetime, timedelta

from pribilka.services.trends_history import (
    _RateEvent,
    _build_carry_forward_series,
    _iter_bucket_starts,
)


def test_carry_forward_keeps_stale_high_rate_visible():
    instrument_a = uuid.uuid4()
    instrument_b = uuid.uuid4()
    now = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)
    since = now - timedelta(days=7)

    events = [
        _RateEvent(
            instrument_id=instrument_a,
            recorded_at=datetime(2026, 6, 8, 10, 0, tzinfo=UTC),
            value=6.8,
        ),
        _RateEvent(
            instrument_id=instrument_b,
            recorded_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
            value=6.0,
        ),
    ]
    buckets = _iter_bucket_starts(since, now, hourly=True)
    series = _build_carry_forward_series(events, buckets, hourly=True)

    assert series.best
    assert series.best[-1].value == 6.8
    assert series.average[-1].value == (6.8 + 6.0) / 2


def test_carry_forward_adds_instrument_when_first_seen():
    instrument = uuid.uuid4()
    bucket = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)
    events = [
        _RateEvent(
            instrument_id=instrument,
            recorded_at=datetime(2026, 7, 13, 5, 30, tzinfo=UTC),
            value=5.5,
        ),
    ]
    series = _build_carry_forward_series(events, [bucket], hourly=True)

    assert len(series.best) == 1
    assert series.best[0].value == 5.5


def test_carry_forward_drops_empty_buckets_before_any_data():
    instrument = uuid.uuid4()
    start = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)
    later = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)
    events = [
        _RateEvent(
            instrument_id=instrument,
            recorded_at=datetime(2026, 7, 13, 7, 30, tzinfo=UTC),
            value=4.0,
        ),
    ]
    series = _build_carry_forward_series(events, [start, later], hourly=True)

    assert len(series.best) == 1
    assert series.best[0].recorded_at == later
    assert series.best[0].value == 4.0
