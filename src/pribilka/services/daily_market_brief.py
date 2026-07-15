"""Daily market brief for admin Telegram."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.models.enums import CountryCode, CurrencyCode
from pribilka.models.financial_instrument import FinancialInstrument
from pribilka.models.fx_rate import FxRate
from pribilka.models.rate_history import RateHistory
from pribilka.services import market_data
from pribilka.services.rental_weekly_stats import collect_rental_weekly_stats
from pribilka.services.telegram import send_admin_telegram
from pribilka.services.trends_history import get_market_trends_history

logger = logging.getLogger(__name__)


def _format_pp(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f} pp".replace(".", ",")


def _format_rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}%".replace(".", ",")


def _format_money(value: float | None, *, decimals: int = 2) -> str:
    if value is None:
        return "n/a"
    text = f"{value:.{decimals}f}".replace(".", ",")
    return text


def _format_signed_money(value: float | None, *, decimals: int = 2) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{_format_money(value, decimals=decimals)}"


def _series_endpoints(points: list) -> tuple[float | None, float | None, float | None]:
    if not points:
        return None, None, None
    start = float(points[0].value)
    end = float(points[-1].value)
    return end, start, end - start


def _fx_day_delta(
    db: Session,
    *,
    country: CountryCode,
    base: CurrencyCode,
) -> tuple[float | None, float | None, float | None]:
    """Return (now, start, delta) for FX mid rate over the last ~24h."""
    fx = db.scalar(
        select(FxRate)
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.country == country,
            FinancialInstrument.is_active.is_(True),
            FxRate.base_currency == base,
        )
        .limit(1)
    )
    if fx is None:
        return None, None, None

    now_rate = float(fx.mid_market_rate) if fx.mid_market_rate is not None else None
    since = datetime.now(UTC) - timedelta(days=1)
    rows = list(
        db.scalars(
            select(RateHistory)
            .where(
                RateHistory.instrument_id == fx.instrument_id,
                RateHistory.value_type == "mid_rate",
                RateHistory.recorded_at >= since,
            )
            .order_by(RateHistory.recorded_at)
        ).all()
    )
    if not rows:
        return now_rate, None, None

    start = float(rows[0].value)
    end = float(rows[-1].value)
    return end, start, end - start


def collect_daily_market_brief(db: Session, country: CountryCode = CountryCode.PL) -> dict:
    today = datetime.now(UTC).date()
    summary = market_data.get_market_summary(db, country)
    history = get_market_trends_history(db, country, days=1)
    rental = collect_rental_weekly_stats(db, days=1)

    dep_now, dep_start, dep_delta = _series_endpoints(history.deposits.best)
    bond_now, bond_start, bond_delta = _series_endpoints(history.bonds.best)
    gold_now, gold_start, gold_delta = _series_endpoints(history.gold.spot)

    best_deposit = (
        float(summary.best_deposit_rate) if summary.best_deposit_rate is not None else dep_now
    )
    best_bond = float(summary.best_bond_yield) if summary.best_bond_yield is not None else bond_now

    usd_now, usd_start, usd_delta = _fx_day_delta(db, country=country, base=CurrencyCode.USD)
    eur_now, eur_start, eur_delta = _fx_day_delta(db, country=country, base=CurrencyCode.EUR)

    return {
        "date": today.isoformat(),
        "country": country.value,
        "deposits": {
            "best_current": best_deposit,
            "best_tracked_now": dep_now,
            "best_tracked_start": dep_start,
            "best_delta_pp": dep_delta,
        },
        "bonds": {
            "best_current": best_bond,
            "best_tracked_now": bond_now,
            "best_tracked_start": bond_start,
            "best_delta_pp": bond_delta,
        },
        "gold": {
            "spot_now": gold_now if gold_now is not None else summary.gold_spot_price,
            "spot_start": gold_start,
            "change": gold_delta,
            "daily_change_percent": summary.gold_daily_change_percent,
        },
        "fx": {
            "usd_pln": usd_now if usd_now is not None else summary.usd_pln_rate,
            "usd_delta": usd_delta,
            "eur_pln": eur_now if eur_now is not None else summary.eur_pln_rate,
            "eur_delta": eur_delta,
        },
        "rental": {
            "available": bool(rental.get("available")),
            "room_count": rental.get("room_count", 2),
            "top_cities": (rental.get("top_yield_cities") or [])[:3],
        },
    }


def format_daily_market_brief_message(brief: dict) -> str:
    deposits = brief["deposits"]
    bonds = brief["bonds"]
    gold = brief["gold"]
    fx = brief["fx"]
    rental = brief["rental"]
    date_label = brief["date"]

    lines = [
        f"📅 *Codzienny skrót rynku* ({date_label})",
        "",
        "*Lokaty i obligacje*",
        (
            f"• Lokaty: {_format_rate(deposits['best_current'])} "
            f"(zmiana 24h: {_format_pp(deposits['best_delta_pp'])})"
        ),
        (
            f"• Obligacje: {_format_rate(bonds['best_current'])} "
            f"(zmiana 24h: {_format_pp(bonds['best_delta_pp'])})"
        ),
        "",
        "*Złoto i FX*",
        (
            f"• Złoto: {_format_money(gold['spot_now'])} zł/g "
            f"({_format_signed_money(gold['change'])} zł; "
            f"{_format_signed_money(gold.get('daily_change_percent'))}%)"
        ),
        (
            f"• USD/PLN: {_format_money(fx['usd_pln'], decimals=4)} "
            f"({_format_signed_money(fx['usd_delta'], decimals=4)})"
        ),
        (
            f"• EUR/PLN: {_format_money(fx['eur_pln'], decimals=4)} "
            f"({_format_signed_money(fx['eur_delta'], decimals=4)})"
        ),
        "",
        f"*Top 3 miasta (wynajem {rental.get('room_count', 2)}-pok.)*",
    ]

    cities = rental.get("top_cities") or []
    if not cities:
        lines.append("• Brak świeżych danych o rentowności.")
    else:
        for index, city in enumerate(cities, start=1):
            name = city.get("name_pl") or city.get("city_slug") or "?"
            yield_now = city.get("yield_now")
            yield_delta = city.get("yield_delta_pp")
            lines.append(
                f"• {index}. *{name}* — {_format_rate(yield_now)} "
                f"({_format_pp(yield_delta)} / 24h)"
            )

    lines.extend(
        [
            "",
            "_Dane informacyjne • ZyskRadar • nie stanowi rekomendacji inwestycyjnej_",
        ]
    )
    return "\n".join(lines)


def send_daily_market_brief(
    db: Session,
    country: CountryCode = CountryCode.PL,
) -> dict:
    brief = collect_daily_market_brief(db, country)
    message = format_daily_market_brief_message(brief)
    sent = send_admin_telegram(message)
    if sent:
        logger.info("Daily market brief sent to Telegram for %s", brief["date"])
    else:
        logger.warning("Daily market brief Telegram delivery skipped or failed")
    return {"sent": sent, "date": brief["date"], "message": message}
