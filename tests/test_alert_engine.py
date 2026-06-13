from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from pribilka.models.alert_notified_instrument import AlertNotifiedInstrument
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode, RiskLevel
from pribilka.models.user_alert import UserAlert
from pribilka.services.alert_engine import (
    MatchCandidate,
    _deposit_matches,
    _score_ok,
    build_digest_message,
    resolve_notification_kind,
)


def _make_alert(**kwargs) -> UserAlert:
    alert = UserAlert(name="Test", user_id="user-1")
    for key, value in kwargs.items():
        setattr(alert, key, value)
    return alert


def _make_deposit(rate: float, term: int, score: float | None = 80):
    deposit = MagicMock()
    deposit.annual_interest_rate = Decimal(str(rate))
    deposit.term_months = term
    instrument = MagicMock()
    instrument.country = CountryCode.PL
    instrument.currency = CurrencyCode.PLN
    instrument.opportunity_score = score
    instrument.risk_level = RiskLevel.LOW
    deposit.instrument = instrument
    return deposit, instrument


def test_score_ok_requires_score_when_alert_has_minimum():
    assert _score_ok(70.0, 80.0) is True
    assert _score_ok(70.0, 60.0) is False
    assert _score_ok(70.0, None) is False
    assert _score_ok(None, None) is True


def test_deposit_matches_minimum_yield_and_score():
    alert = _make_alert(
        minimum_yield=5.0,
        minimum_opportunity_score=70.0,
        asset_class=AssetClass.BANK_DEPOSIT,
    )
    deposit, instrument = _make_deposit(rate=6.0, term=12, score=85.0)
    assert _deposit_matches(alert, deposit, instrument) is True

    deposit_low, _ = _make_deposit(rate=4.0, term=12, score=85.0)
    assert _deposit_matches(alert, deposit_low, deposit_low.instrument) is False


def test_deposit_rejects_when_term_too_long():
    alert = _make_alert(maximum_term_months=6)
    deposit, instrument = _make_deposit(rate=6.0, term=12)
    assert _deposit_matches(alert, deposit, instrument) is False


def test_resolve_notification_kind_new_when_no_row():
    assert resolve_notification_kind(None, 7.2, 80.0) == "new"


def test_resolve_notification_kind_seed_for_legacy_row():
    row = AlertNotifiedInstrument(
        alert_id=uuid4(),
        instrument_id=uuid4(),
        last_notified_yield=None,
        last_notified_rank=None,
    )
    assert resolve_notification_kind(row, 7.2, 80.0) == "seed"


def test_resolve_notification_kind_skips_unchanged():
    row = AlertNotifiedInstrument(
        alert_id=uuid4(),
        instrument_id=uuid4(),
        last_notified_yield=7.2,
        last_notified_rank=80.0,
    )
    assert resolve_notification_kind(row, 7.2, 80.0) is None


def test_resolve_notification_kind_detects_yield_change():
    row = AlertNotifiedInstrument(
        alert_id=uuid4(),
        instrument_id=uuid4(),
        last_notified_yield=7.2,
        last_notified_rank=80.0,
    )
    assert resolve_notification_kind(row, 7.5, 80.0) == "updated"


def test_build_digest_message_single_match():
    title, message = build_digest_message(
        "__zr_preset:deposits",
        [
            MatchCandidate(
                instrument_id=uuid4(),
                label="PKO 7.20%",
                rank_value=80,
                notify_yield=7.2,
            )
        ],
    )
    assert title == "New match"
    assert "PKO 7.20%" in message
    assert "Deposits" in message


def test_build_digest_message_single_updated_match():
    title, message = build_digest_message(
        "__zr_preset:deposits",
        [
            MatchCandidate(
                instrument_id=uuid4(),
                label="PKO 7.50%",
                rank_value=82,
                notify_yield=7.5,
                kind="updated",
            )
        ],
    )
    assert title == "Updated match"
    assert "PKO 7.50%" in message


def test_build_digest_message_multiple_new_matches():
    title, message = build_digest_message(
        "My alert",
        [
            MatchCandidate(instrument_id=uuid4(), label="PKO 7.20%", rank_value=80, notify_yield=7.2),
            MatchCandidate(instrument_id=uuid4(), label="mBank 6.80%", rank_value=70, notify_yield=6.8),
            MatchCandidate(instrument_id=uuid4(), label="ING 6.50%", rank_value=65, notify_yield=6.5),
            MatchCandidate(instrument_id=uuid4(), label="Alior 6.40%", rank_value=60, notify_yield=6.4),
        ],
    )
    assert title == "4 new opportunities"
    assert "PKO 7.20%" in message
    assert "and 1 more" in message


def test_build_digest_message_updated_batch():
    title, message = build_digest_message(
        "My alert",
        [
            MatchCandidate(
                instrument_id=uuid4(),
                label="PKO 7.50%",
                rank_value=82,
                notify_yield=7.5,
                kind="updated",
            ),
            MatchCandidate(
                instrument_id=uuid4(),
                label="mBank 7.00%",
                rank_value=75,
                notify_yield=7.0,
                kind="updated",
            ),
        ],
    )
    assert title == "2 updated opportunities"
    assert "PKO 7.50%" in message
