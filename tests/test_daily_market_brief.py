from pribilka.services.daily_market_brief import format_daily_market_brief_message


def _sample_brief():
    return {
        "date": "2026-07-15",
        "country": "PL",
        "deposits": {
            "best_current": 6.8,
            "best_tracked_now": 6.8,
            "best_tracked_start": 6.5,
            "best_delta_pp": 0.3,
        },
        "bonds": {
            "best_current": 5.9,
            "best_tracked_now": 5.9,
            "best_tracked_start": 5.9,
            "best_delta_pp": 0.0,
        },
        "gold": {
            "spot_now": 492.33,
            "spot_start": 490.0,
            "change": 2.33,
            "daily_change_percent": 0.48,
        },
        "fx": {
            "usd_pln": 3.7755,
            "usd_delta": -0.012,
            "eur_pln": 4.308,
            "eur_delta": 0.005,
        },
        "rental": {
            "available": True,
            "room_count": 2,
            "top_cities": [
                {
                    "city_slug": "lodz",
                    "name_pl": "Łódź",
                    "yield_now": 6.48,
                    "yield_delta_pp": 0.12,
                },
                {
                    "city_slug": "szczecin",
                    "name_pl": "Szczecin",
                    "yield_now": 6.26,
                    "yield_delta_pp": -0.05,
                },
                {
                    "city_slug": "lublin",
                    "name_pl": "Lublin",
                    "yield_now": 6.16,
                    "yield_delta_pp": 0.0,
                },
            ],
        },
    }


def test_format_daily_market_brief_message():
    message = format_daily_market_brief_message(_sample_brief())

    assert "Codzienny skrót rynku" in message
    assert "6,80%" in message
    assert "Łódź" in message
    assert "Szczecin" in message
    assert "Lublin" in message
    assert "+0,12 pp" in message
    assert "USD/PLN" in message


def test_format_daily_market_brief_without_rental():
    brief = _sample_brief()
    brief["rental"] = {"available": False, "room_count": 2, "top_cities": []}
    message = format_daily_market_brief_message(brief)
    assert "Brak świeżych danych" in message
