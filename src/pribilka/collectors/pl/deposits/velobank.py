import re

from bs4 import BeautifulSoup

from pribilka.collectors.pl.deposits.base import BankDepositParser
from pribilka.collectors.pl.deposits.http import fetch_text
from pribilka.collectors.pl.deposits.models import DepositOffer
from pribilka.collectors.pl.deposits.utils import extract_rate_percent, extract_term_from_text

VELO_NOWE_SRODKI_URL = (
    "https://www.velobank.pl/klienci-indywidualni/oszczednosci/lokata-na-nowe-srodki.html"
)
VELO_AKTYWNA_URL = (
    "https://www.velobank.pl/klienci-indywidualni/oszczednosci/velolokata-dla-aktywnych.html"
)


class VeloBankDepositParser(BankDepositParser):
    institution_name = "VeloBank"
    bank_slug = "velobank"
    source_name = "velobank_scraper"

    def parse(self) -> list[DepositOffer]:
        offers: list[DepositOffer] = []
        offers.extend(self._parse_nowe_srodki(fetch_text(VELO_NOWE_SRODKI_URL)))
        offers.extend(self._parse_velolokata_aktywna())
        return self._dedupe(offers)

    def _parse_nowe_srodki(self, html: str) -> list[DepositOffer]:
        text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
        offers: list[DepositOffer] = []

        pattern = re.compile(
            r"na\s+(?P<term>\d+)\s+mies\w*\s*\n\s*(?P<rate>\d+(?:[,.]\d+)?)\s*%",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            term_months = int(match.group("term"))
            rate = extract_rate_percent(match.group("rate"))
            if rate is None:
                continue
            offers.append(
                DepositOffer(
                    institution_name=self.institution_name,
                    product_name=f"Lokata na Nowe Środki {term_months}M",
                    annual_interest_rate=rate,
                    term_months=term_months,
                    source_url=VELO_NOWE_SRODKI_URL,
                    bank_slug=self.bank_slug,
                    minimum_deposit_amount=1000,
                    maximum_deposit_amount=190_000,
                    promotional_rate_requirements="Nowe środki + zgody marketingowe",
                )
            )

        if not offers:
            for rate_match in re.finditer(
                r"(?P<rate>\d+(?:[,.]\d+)?)\s*%\s*w skali roku", text, re.IGNORECASE
            ):
                rate = extract_rate_percent(rate_match.group("rate"))
                if rate is None:
                    continue
                context = text[max(0, rate_match.start() - 80) : rate_match.start()]
                term_months = extract_term_from_text(context) or 3
                offers.append(
                    DepositOffer(
                        institution_name=self.institution_name,
                        product_name=f"Lokata na Nowe Środki {term_months}M",
                        annual_interest_rate=rate,
                        term_months=term_months,
                        source_url=VELO_NOWE_SRODKI_URL,
                        bank_slug=self.bank_slug,
                        minimum_deposit_amount=1000,
                        maximum_deposit_amount=190_000,
                        promotional_rate_requirements="Nowe środki + zgody marketingowe",
                    )
                )

        return offers

    def _parse_velolokata_aktywna(self) -> list[DepositOffer]:
        try:
            html = fetch_text(VELO_AKTYWNA_URL)
        except Exception:
            return []

        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        rate_match = re.search(
            r"(?P<rate>\d+(?:[,.]\d+)?)\s*%\s*(?:w skali roku)?", text, re.IGNORECASE
        )
        if not rate_match:
            return []

        rate = extract_rate_percent(rate_match.group("rate"))
        if rate is None:
            return []

        return [
            DepositOffer(
                institution_name=self.institution_name,
                product_name="VeloLokata dla Aktywnych",
                annual_interest_rate=rate,
                term_months=6,
                source_url=VELO_AKTYWNA_URL,
                bank_slug=self.bank_slug,
                minimum_deposit_amount=1000,
                maximum_deposit_amount=50_000,
                promotional_rate_requirements="Wpływ min. 2000 zł/mies. na konto + zgody marketingowe",
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
