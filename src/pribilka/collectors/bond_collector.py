"""Polish government bonds collector — seed data for MVP."""

from datetime import date, timedelta

from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode


class PolandBondCollector(BaseCollector):
    SEED_DATA = [
        {
            "external_id": "pl-gov-edo-2027",
            "is_government": True,
            "issuer": "Ministerstwo Finansów RP",
            "bond_series": "EDO",
            "isin": "PL0000102390",
            "maturity_date": date(2027, 4, 10),
            "coupon_rate": 6.0,
            "yield_to_maturity": 5.8,
            "market_price": 101.2,
            "currency": CurrencyCode.PLN,
            "source_url": "https://www.gov.pl/web/finanse",
        },
        {
            "external_id": "pl-gov-tos-2030",
            "is_government": True,
            "issuer": "Ministerstwo Finansów RP",
            "bond_series": "TOS",
            "isin": "PL0000104818",
            "maturity_date": date(2030, 1, 25),
            "coupon_rate": 5.5,
            "yield_to_maturity": 5.9,
            "market_price": 98.5,
            "currency": CurrencyCode.PLN,
            "source_url": "https://www.gov.pl/web/finanse",
        },
    ]

    def __init__(self):
        super().__init__(
            CollectorConfig(
                asset_class=AssetClass.GOVERNMENT_BOND,
                country=CountryCode.PL,
                source_name="poland_bonds_seed",
                refresh_interval=timedelta(hours=1),
            )
        )

    def collect(self) -> list[dict]:
        return [{**item, "country": self.country, "source_name": self.config.source_name} for item in self.SEED_DATA]
