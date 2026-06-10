import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

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


def _recent_notification_exists(
    db: Session, alert_id, instrument_id, within_hours: int = 24
) -> bool:
    since = datetime.now(UTC) - timedelta(hours=within_hours)
    existing = db.scalar(
        select(Notification.id).where(
            Notification.alert_id == alert_id,
            Notification.instrument_id == instrument_id,
            Notification.created_at >= since,
        )
    )
    return existing is not None


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


def _notify_match(
    db: Session,
    alert: UserAlert,
    instrument_id,
    title: str,
    message: str,
) -> None:
    notification = Notification(
        user_id=alert.user_id,
        alert_id=alert.id,
        instrument_id=instrument_id,
        title=title,
        message=message,
    )
    db.add(notification)
    db.flush()

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
                "instrument_id": str(instrument_id),
                "alert_id": str(alert.id),
            },
        )


def evaluate_alerts(db: Session, country: CountryCode = CountryCode.PL) -> int:
    """Match active user alerts against current market data. Returns notifications created."""
    alerts = db.scalars(select(UserAlert).where(UserAlert.is_active.is_(True))).all()
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
        for deposit in deposits:
            if not _deposit_matches(alert, deposit, deposit.instrument):
                continue
            if _recent_notification_exists(db, alert.id, deposit.instrument_id):
                continue
            title = "Opportunity Found"
            message = (
                f"{deposit.product_name} at {deposit.institution_name} "
                f"matches alert «{alert.name}» ({float(deposit.annual_interest_rate):.2f}%)."
            )
            _notify_match(db, alert, deposit.instrument_id, title, message)
            created += 1

        for bond in bonds:
            if not _bond_matches(alert, bond, bond.instrument):
                continue
            if _recent_notification_exists(db, alert.id, bond.instrument_id):
                continue
            ytm = float(bond.yield_to_maturity) if bond.yield_to_maturity else float(bond.coupon_rate)
            label = bond.bond_series or bond.issuer
            title = "Alert Triggered"
            message = f"Bond {label} matches alert «{alert.name}» ({ytm:.2f}% yield)."
            _notify_match(db, alert, bond.instrument_id, title, message)
            created += 1

    db.commit()
    logger.info("Alert evaluation created %d notifications", created)
    return created
