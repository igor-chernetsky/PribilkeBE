import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

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
_YIELD_EPSILON = 0.01
_RANK_EPSILON = 0.5

MatchKind = Literal["new", "updated"]


@dataclass(frozen=True)
class MatchCandidate:
    instrument_id: uuid.UUID
    label: str
    rank_value: float
    notify_yield: float
    kind: MatchKind = "new"


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


def _values_changed(
    last_yield: float,
    last_rank: float,
    yield_value: float,
    rank_value: float,
) -> bool:
    return (
        abs(last_yield - yield_value) >= _YIELD_EPSILON
        or abs(last_rank - rank_value) >= _RANK_EPSILON
    )


def resolve_notification_kind(
    row: AlertNotifiedInstrument | None,
    yield_value: float,
    rank_value: float,
) -> MatchKind | Literal["seed"] | None:
    """Decide whether an instrument should trigger a user-visible notification."""
    if row is None:
        return "new"
    if row.last_notified_yield is None or row.last_notified_rank is None:
        return "seed"
    if _values_changed(row.last_notified_yield, row.last_notified_rank, yield_value, rank_value):
        return "updated"
    return None


def _get_notified_row(
    db: Session, alert_id: uuid.UUID, instrument_id: uuid.UUID
) -> AlertNotifiedInstrument | None:
    return db.get(AlertNotifiedInstrument, (alert_id, instrument_id))


def _seed_snapshot(
    db: Session,
    alert_id: uuid.UUID,
    instrument_id: uuid.UUID,
    yield_value: float,
    rank_value: float,
) -> None:
    now = datetime.now(UTC)
    row = db.get(AlertNotifiedInstrument, (alert_id, instrument_id))
    if row is None:
        db.add(
            AlertNotifiedInstrument(
                alert_id=alert_id,
                instrument_id=instrument_id,
                last_notified_at=now,
                last_notified_yield=yield_value,
                last_notified_rank=rank_value,
            )
        )
        return
    row.last_notified_at = now
    row.last_notified_yield = yield_value
    row.last_notified_rank = rank_value


def _mark_instruments_notified(
    db: Session, alert_id: uuid.UUID, matches: list[MatchCandidate]
) -> None:
    now = datetime.now(UTC)
    for match in matches:
        row = db.get(AlertNotifiedInstrument, (alert_id, match.instrument_id))
        if row is None:
            db.add(
                AlertNotifiedInstrument(
                    alert_id=alert_id,
                    instrument_id=match.instrument_id,
                    last_notified_at=now,
                    last_notified_yield=match.notify_yield,
                    last_notified_rank=match.rank_value,
                )
            )
        else:
            row.last_notified_at = now
            row.last_notified_yield = match.notify_yield
            row.last_notified_rank = match.rank_value


def build_digest_message(
    alert_name: str, matches: list[MatchCandidate], max_shown: int = _DIGEST_SHOW_MAX
) -> tuple[str, str]:
    display = _alert_display_name(alert_name)
    sorted_matches = sorted(matches, key=lambda item: item.rank_value, reverse=True)
    count = len(sorted_matches)

    if count == 1:
        match = sorted_matches[0]
        title = "Updated match" if match.kind == "updated" else "New match"
        return (
            title,
            f"{match.label} matches «{display}».",
        )

    shown = sorted_matches[:max_shown]
    body = ", ".join(item.label for item in shown)
    remaining = count - len(shown)
    if remaining > 0:
        body += f" and {remaining} more"

    updated = sum(1 for item in sorted_matches if item.kind == "updated")
    if updated == count:
        title = f"{count} updated opportunities"
    elif updated == 0:
        title = f"{count} new opportunities"
    else:
        title = f"{count} matching opportunities"

    return (
        title,
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


def _consider_match(
    db: Session,
    alert: UserAlert,
    instrument_id: uuid.UUID,
    label: str,
    yield_value: float,
    rank_value: float,
    matches: list[MatchCandidate],
) -> None:
    row = _get_notified_row(db, alert.id, instrument_id)
    kind = resolve_notification_kind(row, yield_value, rank_value)
    if kind is None:
        return
    if kind == "seed":
        _seed_snapshot(db, alert.id, instrument_id, yield_value, rank_value)
        return
    matches.append(
        MatchCandidate(
            instrument_id=instrument_id,
            label=label,
            rank_value=rank_value,
            notify_yield=yield_value,
            kind=kind,
        )
    )


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

    _mark_instruments_notified(db, alert.id, matches)

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
            rate = float(deposit.annual_interest_rate)
            rank = _rank_value(instrument, rate)
            _consider_match(
                db,
                alert,
                instrument.id,
                f"{deposit.institution_name} {rate:.2f}%",
                rate,
                rank,
                matches,
            )

        for bond in bonds:
            instrument = bond.instrument
            if not _bond_matches(alert, bond, instrument):
                continue
            ytm = float(bond.yield_to_maturity) if bond.yield_to_maturity else float(bond.coupon_rate)
            label = bond.bond_series or bond.issuer
            rank = _rank_value(instrument, ytm)
            _consider_match(
                db,
                alert,
                instrument.id,
                f"{label} {ytm:.2f}%",
                ytm,
                rank,
                matches,
            )

        if not matches:
            continue

        _notify_digest(db, alert, matches)
        created += 1

    db.commit()
    logger.info("Alert evaluation created %d digest notifications", created)
    return created
