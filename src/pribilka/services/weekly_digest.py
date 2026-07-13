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
from pribilka.schemas.weekly_digest import DigestHighlights, DigestSection, WeeklyDigestContent
from pribilka.services import market_data
from pribilka.services.push_notifications import send_push_to_user
from pribilka.services.telegram import send_admin_telegram
from pribilka.services.rental_weekly_stats import collect_rental_weekly_stats
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

    stats = {
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
            # Live max from active offers (matches market summary / top picks).
            "best_current": (
                float(summary.best_deposit_rate) if summary.best_deposit_rate is not None else None
            ),
            # Trend series endpoints (hourly buckets in rate_history).
            "best_now": dep_best_now,
            "best_start": dep_best_start,
            "best_delta_pp": dep_best_delta,
            "avg_now": dep_avg_now,
            "avg_start": dep_avg_start,
            "avg_delta_pp": dep_avg_delta,
        },
        "bonds": {
            "best_current": (
                float(summary.best_bond_yield) if summary.best_bond_yield is not None else None
            ),
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
    if country == CountryCode.PL:
        stats["rental"] = collect_rental_weekly_stats(db, days=7)
    else:
        stats["rental"] = {
            "available": False,
            "snapshot_periods": 0,
            "cities": [],
            "top_yield_cities": [],
        }
    return stats


def _format_pp(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f} pp"


def _format_pln(value: float | None, locale: str) -> str:
    if value is None:
        return "brak danych" if locale == "pl" else "n/a"
    text = f"{value:,.0f}".replace(",", " ")
    return f"{text} zł" if locale == "pl" else f"{text} PLN"


def _format_pln_delta(value: float | None, locale: str) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    text = f"{sign}{value:,.0f}".replace(",", " ")
    suffix = " zł" if locale == "pl" else " PLN"
    return f"{text}{suffix}"


def _city_name(city: dict, locale: str) -> str:
    return city["name_pl"] if locale == "pl" else city["name_en"]


def _rental_body(stats: dict, locale: str) -> str:
    rental = stats.get("rental") or {}
    if not rental.get("available"):
        if locale == "pl":
            return (
                "Brak danych o rynku nieruchomości za ostatni tydzień — "
                "kolektor Otodom jeszcze nie zebrał snapshotów w tym okresie."
            )
        return (
            "No residential market data for the past week — "
            "the Otodom collector has not produced snapshots in this period yet."
        )

    periods = rental["snapshot_periods"]
    top = rental["top_yield_cities"]
    leader = top[0]
    leader_name = _city_name(leader, locale)

    if locale == "pl":
        intro = (
            f"Na podstawie {periods} snapshotów z ostatnich 7 dni "
            f"(mieszkania 2-pokojowe, ogłoszenia Otodom). "
            f"Najwyższy szacunkowy yield brutto: {leader_name} — "
            f"{leader['yield_now']:.2f}% ({_format_pp(leader.get('yield_delta_pp'))})."
        )
    else:
        intro = (
            f"Based on {periods} snapshots over the last 7 days "
            f"(2-room Otodom listings). "
            f"Highest estimated gross yield: {leader_name} — "
            f"{leader['yield_now']:.2f}% ({_format_pp(leader.get('yield_delta_pp'))})."
        )

    warsaw = next((city for city in rental["cities"] if city["city_slug"] == "warszawa"), None)
    if warsaw is None:
        return intro

    if locale == "pl":
        detail = (
            f"Warszawa: yield {warsaw['yield_now']:.2f}% "
            f"({_format_pp(warsaw.get('yield_delta_pp'))}), "
            f"mediana sprzedaży {_format_pln(warsaw.get('sale_median_now'), locale)} "
            f"({_format_pln_delta(warsaw.get('sale_median_delta'), locale)}), "
            f"wynajem {_format_pln(warsaw.get('rent_median_now'), locale)}/mies. "
            f"({_format_pln_delta(warsaw.get('rent_median_delta'), locale)})."
        )
    else:
        detail = (
            f"Warsaw: yield {warsaw['yield_now']:.2f}% "
            f"({_format_pp(warsaw.get('yield_delta_pp'))}), "
            f"sale median {_format_pln(warsaw.get('sale_median_now'), locale)} "
            f"({_format_pln_delta(warsaw.get('sale_median_delta'), locale)}), "
            f"rent {_format_pln(warsaw.get('rent_median_now'), locale)}/mo "
            f"({_format_pln_delta(warsaw.get('rent_median_delta'), locale)})."
        )

    return f"{intro} {detail}"


def build_digest_highlights(stats: dict, locale: str) -> DigestHighlights:
    deposits = stats.get("deposits") or {}
    bonds = stats.get("bonds") or {}
    gold = stats.get("gold") or {}
    rental = stats.get("rental") or {}

    gold_change_percent = None
    spot_now = gold.get("spot_now")
    spot_start = gold.get("spot_start")
    if spot_now is not None and spot_start not in (None, 0):
        gold_change_percent = (float(spot_now) - float(spot_start)) / float(spot_start) * 100

    rental_leader_city = None
    rental_leader_yield = None
    if rental.get("available"):
        leaders = rental.get("top_yield_cities") or rental.get("cities") or []
        if leaders:
            leader = leaders[0]
            rental_leader_city = _city_name(leader, locale)
            rental_leader_yield = leader.get("yield_now")

    summary = stats.get("summary") or {}
    best_deposit = deposits.get("best_current") or summary.get("best_deposit_rate")
    best_bond = bonds.get("best_current") or summary.get("best_bond_yield")

    return DigestHighlights(
        best_deposit_rate=best_deposit,
        best_bond_yield=best_bond,
        gold_change_percent=gold_change_percent,
        rental_leader_city=rental_leader_city,
        rental_leader_yield=rental_leader_yield,
    )


def _finalize_content_dict(data: dict, stats: dict, locale: str) -> dict:
    finalized = dict(data)
    finalized["highlights"] = build_digest_highlights(stats, locale).model_dump()
    return finalized


def _build_template_content(stats: dict, locale: str) -> WeeklyDigestContent:
    week_start = stats["week_start"]
    week_end = stats["week_end"]
    deposits = stats["deposits"]
    bonds = stats["bonds"]
    gold = stats["gold"]

    if locale == "pl":
        title = f"Tygodniowy przegląd rynku ({week_start} – {week_end})"
        summary = (
            "Oto skrót zmian na polskim rynku lokat, obligacji skarbowych, złota "
            "i nieruchomości (wynajem) z ostatnich 7 dni. "
            "To podsumowanie informacyjne, nie rekomendacja inwestycyjna."
        )
        sections = [
            DigestSection(
                heading="Lokaty",
                body=(
                    f"Najlepsza dostępna stawka: {deposits['best_current'] or 'brak danych'}%. "
                    f"Zmiana obserwowanej stawki w trendzie vs tydzień temu: "
                    f"{_format_pp(deposits['best_delta_pp'])}. "
                    f"Średnia rynkowa: {deposits['avg_now'] or 'brak danych'}% "
                    f"({_format_pp(deposits['avg_delta_pp'])})."
                ),
            ),
            DigestSection(
                heading="Obligacje skarbowe",
                body=(
                    f"Najlepsza dostępna rentowność: {bonds['best_current'] or 'brak danych'}%. "
                    f"Zmiana obserwowanej rentowności w trendzie vs tydzień temu: "
                    f"{_format_pp(bonds['best_delta_pp'])}. "
                    f"Średnia rynkowa: {bonds['avg_now'] or 'brak danych'}%."
                ),
            ),
            DigestSection(
                heading="Złoto i FX",
                body=(
                    f"Złoto (średni punkt tygodnia): {gold['spot_now'] or 'brak danych'}. "
                    f"USD/PLN: {stats['summary'].get('usd_pln') or 'brak danych'}."
                ),
            ),
            DigestSection(
                heading="Nieruchomości",
                body=_rental_body(stats, locale),
            ),
            DigestSection(
                heading="Warte uwagi",
                body=_top_picks_body(stats, locale),
            ),
        ]
        return WeeklyDigestContent(title=title, summary=summary, sections=sections)

    title = f"Weekly market digest ({week_start} – {week_end})"
    summary = (
        "A concise look at how Polish deposit rates, government bonds, gold, "
        "and residential rental yields moved over the last 7 days. "
        "Informational only — not investment advice."
    )
    sections = [
        DigestSection(
            heading="Deposits",
            body=(
                f"Best available rate: {deposits['best_current'] or 'n/a'}%. "
                f"Tracked best-rate trend vs last week: {_format_pp(deposits['best_delta_pp'])}. "
                f"Market average: {deposits['avg_now'] or 'n/a'}% "
                f"({_format_pp(deposits['avg_delta_pp'])})."
            ),
        ),
        DigestSection(
            heading="Government bonds",
            body=(
                f"Best available yield: {bonds['best_current'] or 'n/a'}%. "
                f"Tracked best-yield trend vs last week: {_format_pp(bonds['best_delta_pp'])}. "
                f"Market average: {bonds['avg_now'] or 'n/a'}%."
            ),
        ),
        DigestSection(
            heading="Gold & FX",
            body=(
                f"Gold (weekly average point): {gold['spot_now'] or 'n/a'}. "
                f"USD/PLN: {stats['summary'].get('usd_pln') or 'n/a'}."
            ),
        ),
        DigestSection(
            heading="Real estate",
            body=_rental_body(stats, locale),
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


_LOCALE_PAYLOAD_KEYS = {
    "en": ("en", "english", "en-us", "en_us"),
    "pl": ("pl", "polish", "pl-pl", "pl_pl", "pol"),
}


def _extract_locale_payload(payload: dict, locale: str) -> dict | None:
    for key in _LOCALE_PAYLOAD_KEYS[locale]:
        value = payload.get(key)
        if isinstance(value, dict):
            return value

    for container_key in ("locales", "languages", "content", "digest", "weekly_digest"):
        container = payload.get(container_key)
        if not isinstance(container, dict):
            continue
        for key in _LOCALE_PAYLOAD_KEYS[locale]:
            value = container.get(key)
            if isinstance(value, dict):
                return value
    return None


def _parse_openai_payload(
    payload: dict, stats: dict
) -> tuple[dict, dict] | None:
    en_data = _extract_locale_payload(payload, "en")
    pl_data = _extract_locale_payload(payload, "pl")

    try:
        content_en = (
            _content_to_dict(WeeklyDigestContent.model_validate(en_data))
            if en_data
            else _content_to_dict(_build_template_content(stats, "en"))
        )
        content_pl = (
            _content_to_dict(WeeklyDigestContent.model_validate(pl_data))
            if pl_data
            else _content_to_dict(_build_template_content(stats, "pl"))
        )
    except Exception:
        return None

    if not en_data and not pl_data:
        return None
    return (
        _finalize_content_dict(content_en, stats, "en"),
        _finalize_content_dict(content_pl, stats, "pl"),
    )


def _build_openai_content(stats: dict) -> tuple[dict, dict] | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    try:
        import httpx

        prompt = (
            "You are a financial market editor for a Poland-focused savings app. "
            "Using ONLY the JSON stats below, write a weekly digest in English and Polish.\n"
            "Return a single JSON object with EXACTLY two top-level keys: \"en\" and \"pl\".\n"
            "Each value must be an object: "
            '{"title":"...","summary":"...","sections":[{"heading":"...","body":"..."}]}\n'
            "Use exactly 5 sections in this order: deposits, government bonds, gold & FX, real estate, top picks.\n"
            "For deposits/bonds sections use deposits.best_current / bonds.best_current as the current best rate.\n"
            "Use deposits.best_delta_pp / bonds.best_delta_pp only for week-over-week trend wording.\n"
            "Top picks must stay consistent with best_current and top_deposits / top_bonds.\n"
            "2-3 sentences per section body. No buy/sell advice. No invented numbers.\n"
            f"STATS:\n{json.dumps(stats, default=str)}"
        )
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Respond with valid JSON only. "
                            "Top-level keys must include both en and pl."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 1800,
            },
            timeout=45,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        payload = json.loads(raw)
        parsed = _parse_openai_payload(payload, stats)
        if parsed is None:
            logger.warning("OpenAI weekly digest JSON unusable: %s", raw[:500])
        return parsed
    except Exception:
        logger.exception("OpenAI weekly digest generation failed")
        return None


def generate_weekly_digest(
    db: Session, country: CountryCode = CountryCode.PL, *, force: bool = False
) -> WeeklyDigest | None:
    week_start, week_end = _week_bounds()
    existing = db.scalar(
        select(WeeklyDigest).where(
            WeeklyDigest.country == country,
            WeeklyDigest.week_start == week_start,
        )
    )
    if existing and not force:
        logger.info("Weekly digest already exists for %s week %s", country, week_start)
        return existing
    if existing and force:
        db.delete(existing)
        db.commit()

    stats = collect_weekly_stats(db, country)
    source = "template"
    openai_content = _build_openai_content(stats)
    if openai_content:
        content_en, content_pl = openai_content
        source = "openai"
    else:
        content_en = _finalize_content_dict(
            _content_to_dict(_build_template_content(stats, "en")),
            stats,
            "en",
        )
        content_pl = _finalize_content_dict(
            _content_to_dict(_build_template_content(stats, "pl")),
            stats,
            "pl",
        )

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
    send_weekly_digest_to_telegram(digest)
    return digest


def pick_digest_content(digest: WeeklyDigest, locale: str) -> WeeklyDigestContent:
    data = digest.content_pl if locale.lower().startswith("pl") else digest.content_en
    return _dict_to_content(data)


def format_digest_telegram_message(digest: WeeklyDigest, locale: str = "pl") -> str:
    content = pick_digest_content(digest, locale)
    lines = [
        f"📊 *{content.title}*",
        "",
        content.summary,
        "",
    ]
    for section in content.sections:
        lines.append(f"*{section.heading}*")
        lines.append(section.body)
        lines.append("")
    lines.append(f"_Źródło: {digest.source} | {digest.week_start} – {digest.week_end}_")
    return "\n".join(lines)


def send_weekly_digest_to_telegram(digest: WeeklyDigest, locale: str = "pl") -> bool:
    message = format_digest_telegram_message(digest, locale)
    sent = send_admin_telegram(message)
    if sent:
        logger.info("Weekly digest sent to Telegram (%s)", digest.id)
    else:
        logger.warning("Weekly digest Telegram delivery skipped or failed (%s)", digest.id)
    return sent


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
