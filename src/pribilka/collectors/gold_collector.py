"""Gold price collector — placeholder using static reference price.

Replace with real source (e.g. NBP gold, broker API) in next iteration.
"""

from datetime import timedelta

from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode


class PolandGoldCollector(BaseCollector):
    def __init__(self):
        super().__init__(
            CollectorConfig(
                asset_class=AssetClass.GOLD,
                country=CountryCode.PL,
                source_name="gold_placeholder",
                refresh_interval=timedelta(minutes=15),
            )
        )

    def collect(self) -> list[dict]:
        # Placeholder — will be replaced with live source
        spot = 285.50
        spread = 2.0
        return [
            {
                "external_id": "gold-pln-gram",
                "spot_price": spot,
                "buy_price": spot + spread,
                "sell_price": spot - spread,
                "country": self.country,
                "currency": CurrencyCode.PLN,
                "source_name": self.config.source_name,
                "source_url": "",
            }
        ]
