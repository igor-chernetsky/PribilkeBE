from datetime import date

from pribilka.services.weekly_digest import (
    _build_template_content,
    _parse_openai_payload,
    _rental_body,
    build_digest_highlights,
    format_digest_telegram_message,
)


def _sample_stats():
    return {
        "week_start": "2026-06-01",
        "week_end": "2026-06-07",
        "summary": {"usd_pln": 4.05},
        "deposits": {
            "best_now": 7.2,
            "best_delta_pp": 0.3,
            "avg_now": 5.1,
            "avg_delta_pp": 0.1,
        },
        "bonds": {
            "best_now": 6.5,
            "best_delta_pp": -0.1,
            "avg_now": 5.8,
            "avg_delta_pp": 0.0,
        },
        "gold": {"spot_now": 285.0, "change": 1.2},
        "top_deposits": [
            {"institution": "PKO", "name": "Lokata", "rate": 7.2},
        ],
        "top_bonds": [
            {"issuer": "MF", "series": "EDO", "yield": 6.5},
        ],
        "rental": {
            "available": True,
            "snapshot_periods": 3,
            "cities": [
                {
                    "city_slug": "krakow",
                    "name_pl": "Kraków",
                    "name_en": "Krakow",
                    "room_count": 2,
                    "yield_now": 5.6,
                    "yield_delta_pp": 0.2,
                    "sale_median_now": 520_000,
                    "sale_median_delta": 10_000,
                    "rent_median_now": 2_700,
                    "rent_median_delta": 50,
                },
                {
                    "city_slug": "warszawa",
                    "name_pl": "Warszawa",
                    "name_en": "Warsaw",
                    "room_count": 2,
                    "yield_now": 5.0,
                    "yield_delta_pp": 0.1,
                    "sale_median_now": 620_000,
                    "sale_median_delta": 5_000,
                    "rent_median_now": 2_600,
                    "rent_median_delta": 100,
                },
            ],
            "top_yield_cities": [],
        },
    }


def test_template_weekly_digest_has_en_and_pl_sections():
    stats = _sample_stats()
    stats["rental"]["top_yield_cities"] = stats["rental"]["cities"][:1]

    en = _build_template_content(stats, "en")
    pl = _build_template_content(stats, "pl")

    assert len(en.sections) == 5
    assert len(pl.sections) == 5
    assert en.sections[3].heading == "Real estate"
    assert pl.sections[3].heading == "Nieruchomości"
    assert "Krakow" in en.sections[3].body
    assert "Kraków" in pl.sections[3].body
    assert "Weekly market digest" in en.title
    assert "Tygodniowy przegląd" in pl.title


def test_rental_body_without_data():
    stats = _sample_stats()
    stats["rental"] = {"available": False}
    body = _rental_body(stats, "pl")
    assert "Brak danych" in body


def test_build_digest_highlights_from_stats():
    stats = _sample_stats()
    stats["gold"]["spot_start"] = 280.0
    stats["gold"]["spot_now"] = 285.0
    stats["rental"]["top_yield_cities"] = stats["rental"]["cities"]

    highlights = build_digest_highlights(stats, "pl")

    assert highlights.best_deposit_rate == 7.2
    assert highlights.best_bond_yield == 6.5
    assert highlights.gold_change_percent is not None
    assert abs(highlights.gold_change_percent - 1.7857) < 0.01
    assert highlights.rental_leader_city == "Kraków"
    assert highlights.rental_leader_yield == 5.6


def test_parse_openai_payload_accepts_nested_locales():
    stats = _sample_stats()
    stats["rental"]["top_yield_cities"] = stats["rental"]["cities"][:1]
    stats["rental"]["available"] = False
    payload = {
        "locales": {
            "english": {
                "title": "Weekly digest",
                "summary": "Summary EN",
                "sections": [
                    {"heading": "Deposits", "body": "Body"},
                    {"heading": "Bonds", "body": "Body"},
                    {"heading": "Gold", "body": "Body"},
                    {"heading": "Real estate", "body": "Body"},
                    {"heading": "Picks", "body": "Body"},
                ],
            }
        }
    }
    result = _parse_openai_payload(payload, stats)
    assert result is not None
    en, pl = result
    assert en["title"] == "Weekly digest"
    assert pl["title"].startswith("Tygodniowy")


def test_format_digest_telegram_message_uses_polish_content():
    from pribilka.models.weekly_digest import WeeklyDigest
    from pribilka.models.enums import CountryCode

    stats = _sample_stats()
    stats["rental"]["top_yield_cities"] = stats["rental"]["cities"][:1]
    stats["top_deposits"] = []
    stats["top_bonds"] = []
    pl_content = _build_template_content(stats, "pl")
    digest = WeeklyDigest(
        country=CountryCode.PL,
        week_start=date.fromisoformat("2026-06-01"),
        week_end=date.fromisoformat("2026-06-07"),
        content_en=pl_content.model_dump(),
        content_pl=pl_content.model_dump(),
        source="template",
    )
    message = format_digest_telegram_message(digest, "pl")
    assert "Tygodniowy przegląd" in message
    assert "*Lokaty*" in message
