"""Polish bank deposit collector.

MVP uses seed data structure; real scraping from bank websites comes next.
Each source gets its own parser class inheriting BaseCollector.
"""

from datetime import timedelta

from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode, InterestCapitalization


class PolandDepositCollector(BaseCollector):
    """Collects deposit offers for Polish market."""

    SEED_DATA = [
        {
            "external_id": "pko-konto-oszczednosciowe-3m",
            "institution_name": "PKO Bank Polski",
            "product_name": "Konto oszczędnościowe 3M",
            "annual_interest_rate": 5.5,
            "term_months": 3,
            "interest_capitalization": InterestCapitalization.MONTHLY,
            "minimum_deposit_amount": 1000,
            "maximum_deposit_amount": None,
            "currency": CurrencyCode.PLN,
            "source_url": "https://www.pkobp.pl",
        },
        {
            "external_id": "ing-lokata-12m",
            "institution_name": "ING Bank Śląski",
            "product_name": "Lokata na 12 miesięcy",
            "annual_interest_rate": 6.2,
            "term_months": 12,
            "interest_capitalization": InterestCapitalization.AT_MATURITY,
            "minimum_deposit_amount": 1000,
            "maximum_deposit_amount": 500000,
            "currency": CurrencyCode.PLN,
            "source_url": "https://www.ing.pl",
        },
        {
            "external_id": "mbank-lokata-promo-6m",
            "institution_name": "mBank",
            "product_name": "Lokata promocyjna 6M",
            "annual_interest_rate": 6.8,
            "term_months": 6,
            "interest_capitalization": InterestCapitalization.AT_MATURITY,
            "minimum_deposit_amount": 5000,
            "maximum_deposit_amount": 200000,
            "promotional_rate_requirements": "Tylko dla nowych klientów",
            "currency": CurrencyCode.PLN,
            "source_url": "https://www.mbank.pl",
        },
    ]

    def __init__(self):
        super().__init__(
            CollectorConfig(
                asset_class=AssetClass.BANK_DEPOSIT,
                country=CountryCode.PL,
                source_name="poland_deposits_seed",
                refresh_interval=timedelta(hours=4),
            )
        )

    def collect(self) -> list[dict]:
        return [{**item, "country": self.country, "source_name": self.config.source_name} for item in self.SEED_DATA]
