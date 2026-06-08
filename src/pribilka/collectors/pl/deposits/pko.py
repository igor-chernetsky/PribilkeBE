import re

from bs4 import BeautifulSoup

from pribilka.collectors.pl.deposits.base import BankDepositParser
from pribilka.collectors.pl.deposits.http import fetch_text
from pribilka.collectors.pl.deposits.models import DepositOffer
from pribilka.collectors.pl.deposits.utils import extract_rate_percent, extract_term_from_text

PKO_LOKATA_URL = (
    "https://www.pkobp.pl/klienci-indywidualni/oszczednosci/lokaty/lokata-terminowa/"
)
PKO_NOWE_SRODKI_URL = (
    "https://www.pkobp.pl/klient-indywidualny/oszczedzanie-inwestycje/lokata-na-nowe-srodki"
)


class PkoDepositParser(BankDepositParser):
    institution_name = "PKO Bank Polski"
    bank_slug = "pko"
    source_name = "pko_scraper"

    def parse(self) -> list[DepositOffer]:
        offers = self._parse_standard_lokata(fetch_text(PKO_LOKATA_URL))
        offers.extend(self._parse_promo_lokata())
        return self._dedupe(offers)

    def _parse_standard_lokata(self, html: str) -> list[DepositOffer]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        offers: list[DepositOffer] = []

        # Table-like blocks: "3 mies." ... "1%" or "1,75%"
        term_rate_pattern = re.compile(
            r"(?P<term>\d+)\s*mies\.?\s*\n\s*(?P<rate>\d+[,.]?\d*)\s*%",
            re.IGNORECASE,
        )
        for match in term_rate_pattern.finditer(text):
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
                    source_url=PKO_LOKATA_URL,
                    bank_slug=self.bank_slug,
                    minimum_deposit_amount=1000,
                )
            )

        if offers:
            return offers

        # Fallback: marketing line "od 1% do 2% na 3, 6 lub 12 mies."
        for term in (3, 6, 12):
            block = re.search(
                rf"{term}\s*mies\.?\s*(?:\n|.){{0,40}}?(?P<rate>\d+[,.]?\d*)\s*%",
                text,
                re.IGNORECASE,
            )
            if block:
                rate = extract_rate_percent(block.group("rate"))
                if rate:
                    offers.append(
                        DepositOffer(
                            institution_name=self.institution_name,
                            product_name=f"Lokata terminowa {term}M",
                            annual_interest_rate=rate,
                            term_months=term,
                            source_url=PKO_LOKATA_URL,
                            bank_slug=self.bank_slug,
                            minimum_deposit_amount=1000,
                        )
                    )
        return offers

    def _parse_promo_lokata(self) -> list[DepositOffer]:
        try:
            html = fetch_text(PKO_NOWE_SRODKI_URL)
        except Exception:
            return []

        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        rate_match = re.search(
            r"(?P<rate>\d+[,.]\d+)\s*%\s*(?:w skali roku|rocznie)?",
            text,
            re.IGNORECASE,
        )
        if not rate_match:
            return []

        rate = extract_rate_percent(rate_match.group("rate"))
        if rate is None:
            return []

        term_months = extract_term_from_text(text) or 3
        max_amount = None
        max_match = re.search(r"do\s+([\d\s]+)\s*zł", text, re.IGNORECASE)
        if max_match:
            max_amount = float(max_match.group(1).replace(" ", ""))

        return [
            DepositOffer(
                institution_name=self.institution_name,
                product_name="Lokata na Nowe Środki",
                annual_interest_rate=rate,
                term_months=term_months,
                source_url=PKO_NOWE_SRODKI_URL,
                bank_slug=self.bank_slug,
                minimum_deposit_amount=1000,
                maximum_deposit_amount=max_amount,
                promotional_rate_requirements="Lokata na nowe środki — warunki promocyjne",
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
