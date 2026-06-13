from datetime import date

from pribilka.services.weekly_digest import (
    _build_template_content,
    _parse_openai_payload,
    format_digest_telegram_message,
)


def test_template_weekly_digest_has_en_and_pl_sections():
    stats = {
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
    }

    en = _build_template_content(stats, "en")
    pl = _build_template_content(stats, "pl")

    assert len(en.sections) == 4
    assert len(pl.sections) == 4
    assert "Weekly market digest" in en.title
    assert "Tygodniowy przegląd" in pl.title


def test_parse_openai_payload_accepts_nested_locales():
    stats = {
        "week_start": "2026-06-01",
        "week_end": "2026-06-07",
        "summary": {},
        "deposits": {"best_now": 7.0, "best_delta_pp": 0, "avg_now": 5.0, "avg_delta_pp": 0},
        "bonds": {"best_now": 6.0, "best_delta_pp": 0, "avg_now": 5.0, "avg_delta_pp": 0},
        "gold": {"spot_now": 280.0, "change": 0},
        "top_deposits": [],
        "top_bonds": [],
    }
    payload = {
        "locales": {
            "english": {
                "title": "Weekly digest",
                "summary": "Summary EN",
                "sections": [
                    {"heading": "Deposits", "body": "Body"},
                    {"heading": "Bonds", "body": "Body"},
                    {"heading": "Gold", "body": "Body"},
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

    stats = {
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
        "top_deposits": [],
        "top_bonds": [],
    }
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
