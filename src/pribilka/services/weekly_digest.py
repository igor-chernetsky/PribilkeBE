import json
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.config import get_settings
from pribilka.models.device_token import DeviceToken
from pribilka.models.enums import CountryCode
from pribilka.models.notification import Notification
from pribilka.models.user_alert import UserAlert
from pribilka.models.weekly_digest import WeeklyDigest
from pribilka.schemas.weekly_digest import DigestSection, WeeklyDigestContent
from pribilka.services import market_data
from pribilka.services.push_notifications import send_push_to_user
from pribilka.services.trends_history import get_market_trends_history

logger = logging.getLogger(__name__)

_WEEKLY_DIGEST_PRESET = "__zr_preset:weeklyDigest"


def _week_bounds(today: date | None = None) -> tuple[date, date]:
    end = today or datetime.now(UTC).date()
    start = end - timedelta(days=7)
    return start, end


def _series_delta(points: list) -> tuple[float | None, float | None, float | None]:
    if not points:
        return None, None, None
    first = points[0].value
    last = points[-1].value
    return last, first, last - first


def collect_weekly_stats(db: Session, country: CountryCode) -> dict:
    week_start, week_end = _week_bounds()
    history = get_market_trends_history(db, country, days=7)
    summary = market_data.get_market_summary(db, country)
    deposits, _ = market_data.list_deposits(db, country=country, page=1, page_size=3)
    bonds, _ = market_data.list_bonds(db, country=country, page=1, page_size=3)

    dep_best_now, dep_best_start, dep_best_delta = _series_delta(history.deposits.best)
    dep_avg_now, dep_avg_start, dep_avg_delta = _series_delta(history.deposits.average)
    bond_best_now, bond_best_start, bond_best_delta = _series_delta(history.bonds.best)
    bond_avg_now, bond_avg_start, bond_avg_delta = _series_delta(history.bonds.average)
    gold_now, gold_start, gold_delta = _series_delta(history.gold.spot)

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "summary": {
            "best_deposit_rate": summary.best_deposit_rate,
            "best_bond_yield": summary.best_bond_yield,
            "usd_pln": summary.usd_pln_rate,
            "eur_pln": summary.eur_pln_rate,
            "gold_spot": summary.gold_spot_price,
        },
        "deposits": {
            "best_now": dep_best_now,
            "best_start": dep_best_start,
            "best_delta_pp": dep_best_delta,
            "avg_now": dep_avg_now,
            "avg_start": dep_avg_start,
            "avg_delta_pp": dep_avg_delta,
        },
        "bonds": {
            "best_now": bond_best_now,
            "best_start": bond_best_start,
            "best_delta_pp": bond_best_delta,
            "avg_now": bond_avg_now,
            "avg_start": bond_avg_start,
            "avg_delta_pp": bond_avg_delta,
        },
        "gold": {
            "spot_now": gold_now,
            "spot_start": gold_start,
            "change": gold_delta,
        },
        "top_deposits": [
            {
                "institution": d.institution_name,
                "name": d.product_name,
                "rate": d.annual_interest_rate,
                "score": d.opportunity_score,
            }
            for d in deposits
        ],
        "top_bonds": [
            {
                "issuer": b.issuer,
                "series": b.bond_series,
                "yield": b.yield_to_maturity or b.coupon_rate,
                "score": b.opportunity_score,
            }
            for b in bonds
        ],
    }


def _format_pp(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f} pp"


def _build_template_content(stats: dict, locale: str) -> WeeklyDigestContent:
    week_start = stats["week_start"]
    week_end = stats["week_end"]
    deposits = stats["deposits"]
    bonds = stats["bonds"]
    gold = stats["gold"]

    if locale == "pl":
        title = f"Tygodniowy przegląd rynku ({week_start} – {week_end})"
        summary = (
            "Oto skrót zmian na polskim rynku lokat, obligacji skarbowych i złota "
            "z ostatnich 7 dni. To podsumowanie informacyjne, nie rekomendacja inwestycyjna."
        )
        sections = [
            DigestSection(
                heading="Lokaty",
                body=(
                    f"Najlepsza obserwowana stawka: {deposits['best_now'] or 'brak danych'}%. "
                    f"Zmiana vs tydzień temu: {_format_pp(deposits['best_delta_pp'])}. "
                    f"Średnia rynkowa: {deposits['avg_now'] or 'brak danych'}% "
                    f"({_format_pp(deposits['avg_delta_pp'])})."
                ),
            ),
            DigestSection(
                heading="Obligacje skarbowe",
                body=(
                    f"Najlepsza obserwowana rentowność: {bonds['best_now'] or 'brak danych'}%. "
                    f"Zmiana vs tydzień temu: {_format_pp(bonds['best_delta_pp'])}. "
                    f"Średnia rynkowa: {bonds['avg_now'] or 'brak danych'}%."
                ),
            ),
            DigestSection(
                heading="Złoto i FX",
                body=(
                    f"Złoto (średni punkt tygodnia): {gold['spot_now'] or 'brak danych'}. "
                    f"USD/PLN: {stats['summary']['usd_pln'] or 'brak danych'}."
                ),
            ),
            DigestSection(
                heading="Warte uwagi",
                body=_top_picks_body(stats, locale),
            ),
        ]
        return WeeklyDigestContent(title=title, summary=summary, sections=sections)

    title = f"Weekly market digest ({week_start} – {week_end})"
    summary = (
        "A concise look at how Polish deposit rates, government bonds, and gold moved "
        "over the last 7 days. Informational only — not investment advice."
    )
    sections = [
        DigestSection(
            heading="Deposits",
            body=(
                f"Best observed rate: {deposits['best_now'] or 'n/a'}%. "
                f"Week-over-week change: {_format_pp(deposits['best_delta_pp'])}. "
                f"Market average: {deposits['avg_now'] or 'n/a'}% "
                f"({_format_pp(deposits['avg_delta_pp'])})."
            ),
        ),
        DigestSection(
            heading="Government bonds",
            body=(
                f"Best observed yield: {bonds['best_now'] or 'n/a'}%. "
                f"Week-over-week change: {_format_pp(bonds['best_delta_pp'])}. "
                f"Market average: {bonds['avg_now'] or 'n/a'}%."
            ),
        ),
        DigestSection(
            heading="Gold & FX",
            body=(
                f"Gold (weekly average point): {gold['spot_now'] or 'n/a'}. "
                f"USD/PLN: {stats['summary']['usd_pln'] or 'n/a'}."
            ),
        ),
        DigestSection(
            heading="Top picks",
            body=_top_picks_body(stats, locale),
        ),
    ]
    return WeeklyDigestContent(title=title, summary=summary, sections=sections)


def _top_picks_body(stats: dict, locale: str) -> str:
    lines: list[str] = []
    for item in stats["top_deposits"][:3]:
        if locale == "pl":
            lines.append(f"• {item['institution']}: {item['rate']:.2f}% — {item['name']}")
        else:
            lines.append(f"• {item['institution']}: {item['rate']:.2f}% — {item['name']}")
    for item in stats["top_bonds"][:2]:
        label = item["series"] or item["issuer"]
        lines.append(f"• {label}: {float(item['yield']):.2f}%")
    return "\n".join(lines) if lines else ("Brak wyróżnionych ofert." if locale == "pl" else "No highlighted offers.")


def _content_to_dict(content: WeeklyDigestContent) -> dict:
    return content.model_dump()


def _dict_to_content(data: dict) -> WeeklyDigestContent:
    return WeeklyDigestContent.model_validate(data)


def _build_openai_content(stats: dict) -> tuple[dict, dict] | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    try:
        import httpx

        prompt = (
            "You are a financial market editor for a Poland-focused savings app. "
            "Using ONLY the JSON stats below, write a weekly digest in English and Polish.\n"
            "Return strict JSON with this shape:\n"
            '{"en":{"title":"...","summary":"...","sections":[{"heading":"...","body":"..."}]},'
            '"pl":{"title":"...","summary":"...","sections":[{"heading":"...","body":"..."}]}}\n'
            "Use exactly 4 sections in this order: deposits, government bonds, gold & FX, top picks.\n"
            "2-3 sentences per section body. No buy/sell advice. No invented numbers.\n"
            f"STATS:\n{json.dumps(stats, default=str)}"
        )
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": 1200,
            },
            timeout=45,
        )
        response.raise_for_status()
        payload = json.loads(response.json()["choices"][0]["message"]["content"])
        en = WeeklyDigestContent.model_validate(payload["en"])
        pl = WeeklyDigestContent.model_validate(payload["pl"])
        return _content_to_dict(en), _content_to_dict(pl)
    except Exception:
        logger.exception("OpenAI weekly digest generation failed")
        return None


def generate_weekly_digest(db: Session, country: CountryCode = CountryCode.PL) -> WeeklyDigest | None:
    week_start, week_end = _week_bounds()
    existing = db.scalar(
        select(WeeklyDigest).where(
            WeeklyDigest.country == country,
            WeeklyDigest.week_start == week_start,
        )
    )
    if existing:
        logger.info("Weekly digest already exists for %s week %s", country, week_start)
        return existing

    stats = collect_weekly_stats(db, country)
    source = "template"
    openai_content = _build_openai_content(stats)
    if openai_content:
        content_en, content_pl = openai_content
        source = "openai"
    else:
        content_en = _content_to_dict(_build_template_content(stats, "en"))
        content_pl = _content_to_dict(_build_template_content(stats, "pl"))

    digest = WeeklyDigest(
        country=country,
        week_start=week_start,
        week_end=week_end,
        content_en=content_en,
        content_pl=content_pl,
        source=source,
    )
    db.add(digest)
    db.commit()
    db.refresh(digest)
    logger.info("Weekly digest created (%s, source=%s)", digest.id, source)
    return digest


def pick_digest_content(digest: WeeklyDigest, locale: str) -> WeeklyDigestContent:
    data = digest.content_pl if locale.lower().startswith("pl") else digest.content_en
    return _dict_to_content(data)


def notify_weekly_digest_subscribers(db: Session, digest: WeeklyDigest) -> int:
    alerts = db.scalars(
        select(UserAlert).where(
            UserAlert.is_active.is_(True),
            UserAlert.name == _WEEKLY_DIGEST_PRESET,
        )
    ).all()
    if not alerts:
        return 0

    sent = 0
    for alert in alerts:
        locale = _user_locale(db, alert.user_id)
        content = pick_digest_content(digest, locale)
        title = content.title
        message = content.summary

        notification = Notification(
            user_id=alert.user_id,
            alert_id=alert.id,
            instrument_id=None,
            group_id=None,
            match_count=1,
            title=title[:255],
            message=message,
        )
        db.add(notification)
        db.flush()

        send_push_to_user(
            db,
            alert.user_id,
            title[:120],
            message[:200],
            data={
                "notification_id": str(notification.id),
                "digest_id": str(digest.id),
                "type": "weekly_digest",
            },
        )
        sent += 1

    db.commit()
    logger.info("Weekly digest notifications sent to %d users", sent)
    return sent


def _user_locale(db: Session, user_id: str) -> str:
    token = db.scalar(
        select(DeviceToken.locale)
        .where(DeviceToken.user_id == user_id, DeviceToken.push_enabled.is_(True))
        .order_by(DeviceToken.updated_at.desc())
    )
    if token and str(token).lower().startswith("pl"):
        return "pl"
    return "en"
