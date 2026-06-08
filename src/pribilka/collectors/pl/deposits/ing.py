import re

from bs4 import BeautifulSoup

from pribilka.collectors.pl.deposits.base import BankDepositParser
from pribilka.collectors.pl.deposits.http import fetch_text
from pribilka.collectors.pl.deposits.models import DepositOffer
from pribilka.collectors.pl.deposits.utils import extract_rate_percent, extract_term_from_text
from pribilka.models.enums import InterestCapitalization

ING_LOKATA_URL = "https://www.ing.pl/indywidualni/inwestycje-i-oszczednosci/lokata-terminowa"


class IngDepositParser(BankDepositParser):
    institution_name = "ING Bank Śląski"
    bank_slug = "ing"
    source_name = "ing_scraper"

    def parse(self) -> list[DepositOffer]:
        html = fetch_text(ING_LOKATA_URL)
        offers = self._parse_pln_deposits(html)
        if not offers:
            offers = self._parse_fallback_regex(html)
        return offers

    def _parse_pln_deposits(self, html: str) -> list[DepositOffer]:
        soup = BeautifulSoup(html, "html.parser")
        offers: list[DepositOffer] = []

        for heading in soup.find_all(["h2", "h3", "h4"]):
            title = heading.get_text(" ", strip=True)
            if "PLN" not in title.upper() or "LOKAT" not in title.upper():
                continue

            section = (
                heading.find_next_sibling(["div", "section"])
                or heading.find_parent(["section", "div"])
                or heading.parent
            )
            if section:
                offers.extend(self._extract_from_section(section))
                break

        return offers

    def _extract_from_section(self, section) -> list[DepositOffer]:
        text = section.get_text("\n", strip=True)
        offers: list[DepositOffer] = []

        pattern = re.compile(
            r"(?P<name>Lokata terminowa(?:\s+Plus)?\s*\d+\s*M)\s*\n\s*"
            r"(?P<rate>\d+(?:[,.]\d+)?)\s*%",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            product_name = match.group("name").strip()
            rate = extract_rate_percent(match.group("rate"))
            term_months = extract_term_from_text(product_name)
            if rate is None or not term_months:
                continue

            offers.append(
                DepositOffer(
                    institution_name=self.institution_name,
                    product_name=product_name,
                    annual_interest_rate=rate,
                    term_months=term_months,
                    source_url=ING_LOKATA_URL,
                    bank_slug=self.bank_slug,
                    interest_capitalization=InterestCapitalization.AT_MATURITY,
                    minimum_deposit_amount=1000,
                )
            )

        return self._dedupe(offers)

    def _parse_fallback_regex(self, html: str) -> list[DepositOffer]:
        pattern = (
            r"(?P<name>Lokata terminowa(?:\s+Plus)?\s*\d+\s*M)\s*</[^>]+>\s*"
            r"(?P<rate>\d+(?:[,.]\d+)?)\s*%"
        )
        offers = []
        for match in re.finditer(pattern, html, re.IGNORECASE):
            product_name = match.group("name").strip()
            rate = extract_rate_percent(match.group("rate"))
            term_months = extract_term_from_text(product_name)
            if rate is None or not term_months:
                continue
            offers.append(
                DepositOffer(
                    institution_name=self.institution_name,
                    product_name=product_name,
                    annual_interest_rate=rate,
                    term_months=term_months,
                    source_url=ING_LOKATA_URL,
                    bank_slug=self.bank_slug,
                    minimum_deposit_amount=1000,
                )
            )
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
