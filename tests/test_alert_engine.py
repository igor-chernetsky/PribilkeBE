from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode, RiskLevel
from pribilka.models.user_alert import UserAlert
from pribilka.services.alert_engine import (
    MatchCandidate,
    _deposit_matches,
    _score_ok,
    build_digest_message,
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


def test_build_digest_message_single_match():
    title, message = build_digest_message(
        "__zr_preset:deposits",
        [MatchCandidate(instrument_id=uuid4(), label="PKO 7.20%", rank_value=80)],
    )
    assert title == "New opportunity"
    assert "PKO 7.20%" in message
    assert "Deposits" in message


def test_build_digest_message_multiple_matches():
    title, message = build_digest_message(
        "My alert",
        [
            MatchCandidate(instrument_id=uuid4(), label="PKO 7.20%", rank_value=80),
            MatchCandidate(instrument_id=uuid4(), label="mBank 6.80%", rank_value=70),
            MatchCandidate(instrument_id=uuid4(), label="ING 6.50%", rank_value=65),
            MatchCandidate(instrument_id=uuid4(), label="Alior 6.40%", rank_value=60),
        ],
    )
    assert title == "4 new opportunities"
    assert "PKO 7.20%" in message
    assert "and 1 more" in message
