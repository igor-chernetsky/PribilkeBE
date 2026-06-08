from pribilka.collectors.fx_collector import NbpFxCollector
from pribilka.collectors.gold_collector import PolandGoldCollector


def test_gold_collector_parses_nbp_entries():
    collector = PolandGoldCollector()
    entries = [
        {"data": "2026-06-05", "cena": 520.0},
        {"data": "2026-06-08", "cena": 522.08},
    ]

    # Test internal logic via patched entries
    collector._fetch_gold_entries = lambda: entries  # type: ignore[method-assign]
    records = collector.collect()

    assert len(records) == 1
    assert records[0]["spot_price"] == 522.08
    assert records[0]["daily_change_percent"] == 0.4
    assert records[0]["source_name"] == "nbp_gold"


def test_fx_collector_computes_daily_change():
    collector = NbpFxCollector()
    collector._fetch_tables = lambda: [  # type: ignore[method-assign]
        {
            "effectiveDate": "2026-06-05",
            "rates": [{"code": "USD", "mid": 3.6392}, {"code": "EUR", "mid": 4.2348}],
        },
        {
            "effectiveDate": "2026-06-08",
            "rates": [{"code": "USD", "mid": 3.6898}, {"code": "EUR", "mid": 4.2462}],
        },
    ]

    records = collector.collect()
    usd = next(r for r in records if r["base_currency"].value == "USD")
    assert usd["mid_market_rate"] == 3.6898
    assert usd["daily_change_percent"] == 1.39
