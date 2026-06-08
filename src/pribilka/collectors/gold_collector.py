"""Gold price collector — NBP official fixing price (PLN/gram)."""

from datetime import timedelta
from decimal import Decimal

import httpx

from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode

NBP_GOLD_LAST_URL = "https://api.nbp.pl/api/cenyzlota/last/2/?format=json"
NBP_GOLD_URL = "https://api.nbp.pl/api/cenyzlota/?format=json"


class PolandGoldCollector(BaseCollector):
    def __init__(self):
        super().__init__(
            CollectorConfig(
                asset_class=AssetClass.GOLD,
                country=CountryCode.PL,
                source_name="nbp_gold",
                refresh_interval=timedelta(minutes=15),
            )
        )

    def collect(self) -> list[dict]:
        entries = self._fetch_gold_entries()
        if not entries:
            return []

        latest = entries[-1]
        spot = float(latest["cena"])
        spread = spot * 0.002  # ~0.2% synthetic dealer spread

        daily_change_percent = None
        if len(entries) >= 2:
            previous = float(entries[-2]["cena"])
            if previous:
                daily_change_percent = round((spot - previous) / previous * 100, 3)

        return [
            {
                "external_id": "gold-pln-gram",
                "spot_price": spot,
                "buy_price": round(spot + spread, 4),
                "sell_price": round(spot - spread, 4),
                "daily_change_percent": daily_change_percent,
                "country": self.country,
                "currency": CurrencyCode.PLN,
                "source_name": self.config.source_name,
                "source_url": NBP_GOLD_URL,
                "price_date": latest.get("data"),
            }
        ]

    def _fetch_gold_entries(self) -> list[dict]:
        headers = {"Accept": "application/json"}
        try:
            response = httpx.get(NBP_GOLD_LAST_URL, headers=headers, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                return data
        except httpx.HTTPError:
            pass

        response = httpx.get(NBP_GOLD_URL, headers=headers, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else [data]
