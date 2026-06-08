import re

from bs4 import BeautifulSoup

from pribilka.collectors.pl.deposits.base import BankDepositParser
from pribilka.collectors.pl.deposits.http import fetch_text
from pribilka.collectors.pl.deposits.models import DepositOffer
from pribilka.collectors.pl.deposits.utils import extract_rate_percent

MBANK_PROMO_URL = (
    "https://www.mbank.pl/indywidualny/inwestycje-i-oszczednosci/lokaty/promocyjna-lokata-na-3msc/"
)
MBANK_FUND_URL = (
    "https://www.mbank.pl/indywidualny/inwestycje-i-oszczednosci/fundusze/lokata-z-funduszem/"
)
MBANK_LOKATY_URL = "https://www.mbank.pl/indywidualny/inwestycje-i-oszczednosci/lokaty/"


class MBankDepositParser(BankDepositParser):
    institution_name = "mBank"
    bank_slug = "mbank"
    source_name = "mbank_scraper"

    def parse(self) -> list[DepositOffer]:
        offers: list[DepositOffer] = []
        offers.extend(self._parse_promo_lokata())
        offers.extend(self._parse_lokata_z_funduszem())
        offers.extend(self._parse_overview())
        return self._dedupe(offers)

    def _parse_promo_lokata(self) -> list[DepositOffer]:
        return self._parse_promo_html(fetch_text(MBANK_PROMO_URL))

    def _parse_promo_html(self, html: str) -> list[DepositOffer]:
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        offers: list[DepositOffer] = []

        for rate_match in re.finditer(r"(?P<rate>\d+[,.]\d+)\s*%\s*w skali roku", text):
            rate = extract_rate_percent(rate_match.group("rate"))
            if rate is None:
                continue
            offers.append(
                DepositOffer(
                    institution_name=self.institution_name,
                    product_name="Lokata na nowe środki",
                    annual_interest_rate=rate,
                    term_months=3,
                    source_url=MBANK_PROMO_URL,
                    bank_slug=self.bank_slug,
                    minimum_deposit_amount=1000,
                    promotional_rate_requirements="Promocja na nowe środki",
                )
            )

        return offers

    def _parse_lokata_z_funduszem(self) -> list[DepositOffer]:
        try:
            html = fetch_text(MBANK_FUND_URL)
        except Exception:
            return []

        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        offers: list[DepositOffer] = []

        variants = [
            (r"6[,.]5\s*%\s*w skali roku\s+dla wariantu 30%", "Lokata z funduszem 30/70", 12),
            (r"4[,.]8\s*%\s*w skali roku\s+dla wariantu 50%", "Lokata z funduszem 50/50", 12),
        ]
        for pattern, name, term in variants:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            rate = extract_rate_percent(match.group(0))
            if rate is None:
                continue
            offers.append(
                DepositOffer(
                    institution_name=self.institution_name,
                    product_name=name,
                    annual_interest_rate=rate,
                    term_months=term,
                    source_url=MBANK_FUND_URL,
                    bank_slug=self.bank_slug,
                    minimum_deposit_amount=10000,
                    promotional_rate_requirements="Wymaga inwestycji w fundusz i zlecenia stałego",
                )
            )

        return offers

    def _parse_overview(self) -> list[DepositOffer]:
        try:
            html = fetch_text(MBANK_LOKATY_URL)
        except Exception:
            return []

        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        match = re.search(
            r"lokata z funduszem.*?do\s+(?P<rate>\d+[,.]\d+)\s*%",
            text,
            re.IGNORECASE,
        )
        if not match:
            return []

        rate = extract_rate_percent(match.group("rate"))
        if rate is None:
            return []

        return [
            DepositOffer(
                institution_name=self.institution_name,
                product_name="Lokata z funduszem (max)",
                annual_interest_rate=rate,
                term_months=12,
                source_url=MBANK_LOKATY_URL,
                bank_slug=self.bank_slug,
                minimum_deposit_amount=10000,
                promotional_rate_requirements="Oferta łączona z funduszem inwestycyjnym",
            )
        ]

    def _dedupe(self, offers: list[DepositOffer]) -> list[DepositOffer]:
        seen: set[str] = set()
        unique: list[DepositOffer] = []
        for offer in offers:
            if offer.external_id in seen:
                continue
            seen.add(offer.external_id)
            unique.append(offer)
        return unique
