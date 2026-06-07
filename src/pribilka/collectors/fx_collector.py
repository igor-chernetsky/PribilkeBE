"""FX rate collector — uses NBP public API (free, no auth required)."""

from datetime import timedelta
from decimal import Decimal

import httpx

from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode

NBP_TABLE_A_URL = "https://api.nbp.pl/api/exchangerates/tables/A/?format=json"


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
        response = httpx.get(NBP_TABLE_A_URL, timeout=15.0)
        response.raise_for_status()
        table = response.json()[0]

        records = []
        for rate_entry in table["rates"]:
            code = rate_entry["code"]
            try:
                base = CurrencyCode(code)
            except ValueError:
                continue

            if base not in self.TARGET_CURRENCIES:
                continue

            mid = Decimal(str(rate_entry["mid"]))
            spread = mid * Decimal("0.001")

            records.append(
                {
                    "external_id": f"{base.value}-PLN",
                    "base_currency": base,
                    "quote_currency": CurrencyCode.PLN,
                    "bid_price": float(mid - spread),
                    "ask_price": float(mid + spread),
                    "mid_market_rate": float(mid),
                    "country": self.country,
                    "currency": CurrencyCode.PLN,
                    "source_name": self.config.source_name,
                    "source_url": NBP_TABLE_A_URL,
                }
            )

        return records
