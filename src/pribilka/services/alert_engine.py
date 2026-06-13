import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from pribilka.models.alert_notified_instrument import AlertNotifiedInstrument
from pribilka.models.bank_deposit import BankDeposit
from pribilka.models.bond import Bond
from pribilka.models.device_token import DeviceToken
from pribilka.models.enums import AssetClass, CountryCode, RiskLevel
from pribilka.models.financial_instrument import FinancialInstrument
from pribilka.models.notification import Notification
from pribilka.models.user_alert import UserAlert
from pribilka.services.push_notifications import send_push_to_user

logger = logging.getLogger(__name__)

_RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}

_DEPOSIT_ASSET_CLASSES = {AssetClass.BANK_DEPOSIT}
_BOND_ASSET_CLASSES = {AssetClass.GOVERNMENT_BOND, AssetClass.CORPORATE_BOND}

_PRESET_PREFIX = "__zr_preset:"
_PRESET_LABELS = {
    "deposits": "Deposits",
    "govBonds": "Government bonds",
    "topOpportunities": "Top opportunities",
}

_DIGEST_SHOW_MAX = 3
_COOLDOWN_HOURS = 24


@dataclass(frozen=True)
class MatchCandidate:
    instrument_id: uuid.UUID
    label: str
    rank_value: float


def _risk_ok(alert_risk: RiskLevel | None, instrument_risk: RiskLevel) -> bool:
    if alert_risk is None:
        return True
    return _RISK_ORDER.get(instrument_risk, 1) <= _RISK_ORDER.get(alert_risk, 1)


def _score_ok(alert_min: float | None, score: float | None) -> bool:
    if alert_min is None:
        return True
    if score is None:
        return False
    return score >= alert_min


def _alert_display_name(alert_name: str) -> str:
    if alert_name.startswith(_PRESET_PREFIX):
        key = alert_name.removeprefix(_PRESET_PREFIX)
        return _PRESET_LABELS.get(key, key)
    return alert_name


def _was_recently_notified(
    db: Session, alert_id: uuid.UUID, instrument_id: uuid.UUID, within_hours: int = _COOLDOWN_HOURS
) -> bool:
    since = datetime.now(UTC) - timedelta(hours=within_hours)
    row = db.scalar(
        select(AlertNotifiedInstrument.last_notified_at).where(
            AlertNotifiedInstrument.alert_id == alert_id,
            AlertNotifiedInstrument.instrument_id == instrument_id,
            AlertNotifiedInstrument.last_notified_at >= since,
        )
    )
    return row is not None


def _mark_instruments_notified(
    db: Session, alert_id: uuid.UUID, instrument_ids: list[uuid.UUID]
) -> None:
    now = datetime.now(UTC)
    for instrument_id in instrument_ids:
        row = db.get(AlertNotifiedInstrument, (alert_id, instrument_id))
        if row is None:
            db.add(
                AlertNotifiedInstrument(
                    alert_id=alert_id,
                    instrument_id=instrument_id,
                    last_notified_at=now,
                )
            )
        else:
            row.last_notified_at = now


def build_digest_message(
    alert_name: str, matches: list[MatchCandidate], max_shown: int = _DIGEST_SHOW_MAX
) -> tuple[str, str]:
    display = _alert_display_name(alert_name)
    sorted_matches = sorted(matches, key=lambda item: item.rank_value, reverse=True)
    count = len(sorted_matches)

    if count == 1:
        match = sorted_matches[0]
        return (
            "New opportunity",
            f"{match.label} matches «{display}».",
        )

    shown = sorted_matches[:max_shown]
    body = ", ".join(item.label for item in shown)
    remaining = count - len(shown)
    if remaining > 0:
        body += f" and {remaining} more"

    return (
        f"{count} new opportunities",
        f"«{display}»: {body}.",
    )


def _deposit_matches(alert: UserAlert, deposit: BankDeposit, instrument: FinancialInstrument) -> bool:
    if alert.asset_class and alert.asset_class not in _DEPOSIT_ASSET_CLASSES:
        return False
    if alert.country and instrument.country != alert.country:
        return False
    if alert.currency and instrument.currency != alert.currency:
        return False
    if alert.minimum_yield is not None and float(deposit.annual_interest_rate) < alert.minimum_yield:
        return False
    if alert.maximum_term_months is not None and deposit.term_months > alert.maximum_term_months:
        return False
    if not _score_ok(
        float(alert.minimum_opportunity_score) if alert.minimum_opportunity_score else None,
        float(instrument.opportunity_score) if instrument.opportunity_score else None,
    ):
        return False
    return _risk_ok(alert.risk_level, instrument.risk_level)


def _bond_matches(alert: UserAlert, bond: Bond, instrument: FinancialInstrument) -> bool:
    if alert.asset_class:
        if alert.asset_class == AssetClass.GOVERNMENT_BOND and instrument.asset_class != AssetClass.GOVERNMENT_BOND:
            return False
        if alert.asset_class == AssetClass.CORPORATE_BOND and instrument.asset_class != AssetClass.CORPORATE_BOND:
            return False
        if alert.asset_class == AssetClass.BANK_DEPOSIT:
            return False
    if alert.country and instrument.country != alert.country:
        return False
    if alert.currency and instrument.currency != alert.currency:
        return False

    ytm = float(bond.yield_to_maturity) if bond.yield_to_maturity else float(bond.coupon_rate)
    if alert.minimum_yield is not None and ytm < alert.minimum_yield:
        return False

    if alert.maximum_term_months is not None:
        now = datetime.now(UTC)
        months_to_maturity = max(
            0,
            (bond.maturity_date.year - now.year) * 12 + bond.maturity_date.month - now.month,
        )
        if months_to_maturity > alert.maximum_term_months:
            return False

    if not _score_ok(
        float(alert.minimum_opportunity_score) if alert.minimum_opportunity_score else None,
        float(instrument.opportunity_score) if instrument.opportunity_score else None,
    ):
        return False
    return _risk_ok(alert.risk_level, instrument.risk_level)


def _rank_value(instrument: FinancialInstrument, yield_value: float) -> float:
    if instrument.opportunity_score is not None:
        return float(instrument.opportunity_score)
    return yield_value


def _notify_digest(
    db: Session,
    alert: UserAlert,
    matches: list[MatchCandidate],
) -> None:
    if not matches:
        return

    title, message = build_digest_message(alert.name, matches)
    group_id = uuid.uuid4()

    notification = Notification(
        user_id=alert.user_id,
        alert_id=alert.id,
        instrument_id=None,
        group_id=group_id,
        match_count=len(matches),
        title=title,
        message=message,
    )
    db.add(notification)
    db.flush()

    _mark_instruments_notified(
        db,
        alert.id,
        [match.instrument_id for match in matches],
    )

    has_push = db.scalar(
        select(DeviceToken.id).where(
            DeviceToken.user_id == alert.user_id,
            DeviceToken.push_enabled.is_(True),
        )
    )
    if has_push:
        send_push_to_user(
            db,
            alert.user_id,
            title,
            message,
            data={
                "notification_id": str(notification.id),
                "alert_id": str(alert.id),
                "group_id": str(group_id),
                "match_count": str(len(matches)),
            },
        )


def evaluate_alerts(db: Session, country: CountryCode = CountryCode.PL) -> int:
    """Match active user alerts and create one digest notification per alert."""
    alerts = db.scalars(
        select(UserAlert).where(
            UserAlert.is_active.is_(True),
            UserAlert.name != "__zr_preset:weeklyDigest",
        )
    ).all()
    if not alerts:
        return 0

    created = 0

    deposits = db.scalars(
        select(BankDeposit)
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.is_active.is_(True),
            FinancialInstrument.country == country,
            FinancialInstrument.asset_class == AssetClass.BANK_DEPOSIT,
        )
        .options(joinedload(BankDeposit.instrument))
    ).all()

    bonds = db.scalars(
        select(Bond)
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.is_active.is_(True),
            FinancialInstrument.country == country,
            FinancialInstrument.asset_class.in_(_BOND_ASSET_CLASSES),
        )
        .options(joinedload(Bond.instrument))
    ).all()

    for alert in alerts:
        matches: list[MatchCandidate] = []

        for deposit in deposits:
            instrument = deposit.instrument
            if not _deposit_matches(alert, deposit, instrument):
                continue
            if _was_recently_notified(db, alert.id, instrument.id):
                continue
            rate = float(deposit.annual_interest_rate)
            matches.append(
                MatchCandidate(
                    instrument_id=instrument.id,
                    label=f"{deposit.institution_name} {rate:.2f}%",
                    rank_value=_rank_value(instrument, rate),
                )
            )

        for bond in bonds:
            instrument = bond.instrument
            if not _bond_matches(alert, bond, instrument):
                continue
            if _was_recently_notified(db, alert.id, instrument.id):
                continue
            ytm = float(bond.yield_to_maturity) if bond.yield_to_maturity else float(bond.coupon_rate)
            label = bond.bond_series or bond.issuer
            matches.append(
                MatchCandidate(
                    instrument_id=instrument.id,
                    label=f"{label} {ytm:.2f}%",
                    rank_value=_rank_value(instrument, ytm),
                )
            )

        if not matches:
            continue

        _notify_digest(db, alert, matches)
        created += 1

    db.commit()
    logger.info("Alert evaluation created %d digest notifications", created)
    return created
