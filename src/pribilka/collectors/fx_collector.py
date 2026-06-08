"""FX rate collector — NBP Table A (free, no auth required)."""

from datetime import timedelta
from decimal import Decimal

import httpx

from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode

NBP_TABLE_A_URL = "https://api.nbp.pl/api/exchangerates/tables/A/?format=json"
NBP_TABLE_A_LAST_URL = "https://api.nbp.pl/api/exchangerates/tables/A/last/2/?format=json"


class NbpFxCollector(BaseCollector):
    TARGET_CURRENCIES = [CurrencyCode.USD, CurrencyCode.EUR, CurrencyCode.GBP, CurrencyCode.CHF]

    def __init__(self):
        super().__init__(
            CollectorConfig(
                asset_class=AssetClass.FOREIGN_EXCHANGE,
                country=CountryCode.PL,
                source_name="nbp_table_a",
                refresh_interval=timedelta(minutes=15),
            )
        )

    def collect(self) -> list[dict]:
        tables = self._fetch_tables()
        if not tables:
            return []

        current = tables[-1]
        previous_rates = {}
        if len(tables) >= 2:
            previous_rates = {
                entry["code"]: Decimal(str(entry["mid"])) for entry in tables[-2]["rates"]
            }

        records = []
        for rate_entry in current["rates"]:
            code = rate_entry["code"]
            try:
                base = CurrencyCode(code)
            except ValueError:
                continue

            if base not in self.TARGET_CURRENCIES:
                continue

            mid = Decimal(str(rate_entry["mid"]))
            spread = mid * Decimal("0.001")

            daily_change_percent = None
            prev = previous_rates.get(code)
            if prev and prev > 0:
                daily_change_percent = float(round((mid - prev) / prev * Decimal("100"), 3))

            records.append(
                {
                    "external_id": f"{base.value}-PLN",
                    "base_currency": base,
                    "quote_currency": CurrencyCode.PLN,
                    "bid_price": float(mid - spread),
                    "ask_price": float(mid + spread),
                    "mid_market_rate": float(mid),
                    "daily_change_percent": daily_change_percent,
                    "country": self.country,
                    "currency": CurrencyCode.PLN,
                    "source_name": self.config.source_name,
                    "source_url": NBP_TABLE_A_URL,
                    "effective_date": current.get("effectiveDate"),
                }
            )

        return records

    def _fetch_tables(self) -> list[dict]:
        headers = {"Accept": "application/json"}
        try:
            response = httpx.get(NBP_TABLE_A_LAST_URL, headers=headers, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                return data
        except httpx.HTTPError:
            pass

        response = httpx.get(NBP_TABLE_A_URL, headers=headers, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else [data]
