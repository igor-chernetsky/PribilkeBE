import re

from bs4 import BeautifulSoup

from pribilka.collectors.pl.deposits.base import BankDepositParser
from pribilka.collectors.pl.deposits.http import fetch_text
from pribilka.collectors.pl.deposits.models import DepositOffer
from pribilka.collectors.pl.deposits.utils import extract_rate_percent

SANTANDER_LOKATA_URL = (
    "https://www.santander.pl/klient-indywidualny/oszczednosci-i-inwestycje/lokata-terminowa"
)


class SantanderDepositParser(BankDepositParser):
    institution_name = "Santander Bank Polska"
    bank_slug = "santander"
    source_name = "santander_scraper"

    def parse(self) -> list[DepositOffer]:
        html = fetch_text(SANTANDER_LOKATA_URL)
        return self._parse_html(html)

    def _parse_html(self, html: str) -> list[DepositOffer]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        offers: list[DepositOffer] = []

        patterns = [
            re.compile(
                r"(?P<term>\d+)\s*mies\w*\s*\n\s*(?P<rate>\d+(?:[,.]\d+)?)\s*%",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?P<term>\d+)\s*mies\.?\s*\n\s*(?P<rate>\d+(?:[,.]\d+)?)\s*%",
                re.IGNORECASE,
            ),
        ]

        for pattern in patterns:
            for match in pattern.finditer(text):
                term_months = int(match.group("term"))
                rate = extract_rate_percent(match.group("rate"))
                if rate is None or term_months not in (1, 2, 3, 6, 9, 12, 18, 24, 36):
                    continue
                offers.append(
                    DepositOffer(
                        institution_name=self.institution_name,
                        product_name=f"Lokata terminowa {term_months}M",
                        annual_interest_rate=rate,
                        term_months=term_months,
                        source_url=SANTANDER_LOKATA_URL,
                        bank_slug=self.bank_slug,
                        minimum_deposit_amount=1000,
                        maximum_deposit_amount=1_000_000,
                    )
                )
            if offers:
                break

        return self._dedupe(offers)

    def _dedupe(self, offers: list[DepositOffer]) -> list[DepositOffer]:
        seen: set[str] = set()
        unique: list[DepositOffer] = []
        for offer in offers:
            if offer.external_id in seen:
                continue
            seen.add(offer.external_id)
            unique.append(offer)
        return unique
