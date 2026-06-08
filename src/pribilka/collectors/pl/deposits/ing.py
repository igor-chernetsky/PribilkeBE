import re

from bs4 import BeautifulSoup

from pribilka.collectors.pl.deposits.base import BankDepositParser
from pribilka.collectors.pl.deposits.http import fetch_bytes, fetch_text, is_bot_wall
from pribilka.collectors.pl.deposits.models import DepositOffer
from pribilka.collectors.pl.deposits.utils import extract_rate_percent, extract_term_from_text
from pribilka.models.enums import InterestCapitalization

ING_LOKATA_URL = "https://www.ing.pl/indywidualni/inwestycje-i-oszczednosci/lokata-terminowa"
ING_RATES_TABLE_URL = (
    "https://www.ing.pl/indywidualni/tabele-i-regulaminy/oprocentowanie/"
    "rachunki-oszczednosciowe-lokaty"
)
# Official PDF rate table — not behind Imperva bot wall (unlike marketing pages).
ING_RATES_PDF_URL = "https://www.ing.pl/_fileserver/item/ebnmasl"

_STANDARD_PRODUCTS = {
    3: "Lokata terminowa 3M",
    6: "Lokata terminowa 6M",
    12: "Lokata terminowa 12M",
}
_PLUS_PRODUCTS = {
    6: "Lokata terminowa Plus 6M",
    12: "Lokata terminowa Plus 12M",
}


class IngDepositParser(BankDepositParser):
    institution_name = "ING Bank Śląski"
    bank_slug = "ing"
    source_name = "ing_scraper"

    def parse(self) -> list[DepositOffer]:
        offers = self._parse_rates_pdf(fetch_bytes(ING_RATES_PDF_URL))
        if not offers:
            offers = self._parse_rates_table(fetch_text(ING_RATES_TABLE_URL))
        if not offers:
            html = fetch_text(ING_LOKATA_URL)
            if not is_bot_wall(html):
                offers = self._parse_pln_deposits(html)
                if not offers:
                    offers = self._parse_fallback_regex(html)
        return offers

    def _parse_rates_pdf(self, content: bytes) -> list[DepositOffer]:
        text = ""
        for encoding in ("cp1250", "latin-1", "utf-8"):
            decoded = content.decode(encoding, errors="ignore")
            if "Lokata terminowa" in decoded or "miesi" in decoded:
                text = decoded
                break
        if not text:
            return []

        parts = re.split(r"PLUS.*?Lokata terminowa", text, maxsplit=1, flags=re.IGNORECASE)
        standard_block = parts[0]
        plus_block = parts[1] if len(parts) > 1 else ""

        offers: list[DepositOffer] = []
        offers.extend(self._parse_term_rate_zip_block(standard_block, _STANDARD_PRODUCTS))
        offers.extend(
            self._parse_term_rate_zip_block(
                plus_block,
                _PLUS_PRODUCTS,
                maximum_by_term={6: 50_000, 12: 100_000},
            )
        )
        return self._dedupe(offers)

    def _parse_term_rate_zip_block(
        self,
        block: str,
        products: dict[int, str],
        maximum_by_term: dict[int, float] | None = None,
    ) -> list[DepositOffer]:
        """PDF tables often list all terms first, then rates."""
        terms = [int(value) for value in re.findall(r"(\d+)\s*miesi\w*", block, re.IGNORECASE)]
        rates = [
            extract_rate_percent(value)
            for value in re.findall(r"(\d+(?:[,.]\d+)?)\s*%", block)
        ]
        rates = [rate for rate in rates if rate is not None]

        offers: list[DepositOffer] = []
        for term_months, rate in zip(terms, rates, strict=False):
            product_name = products.get(term_months)
            if not product_name or rate is None:
                continue
            offers.append(
                self._make_offer(
                    product_name,
                    rate,
                    term_months,
                    maximum_deposit_amount=(
                        maximum_by_term.get(term_months) if maximum_by_term else None
                    ),
                )
            )
        return offers

    def _parse_term_rate_block(
        self,
        block: str,
        products: dict[int, str],
        maximum_by_term: dict[int, float] | None = None,
    ) -> list[DepositOffer]:
        pair_pattern = re.compile(
            r"(?P<term>\d+)\s*miesi\w*"
            r"(?:[\s\S]{0,120}?)"
            r"(?P<rate>\d+(?:[,.]\d+)?)\s*%",
            re.IGNORECASE,
        )

        offers: list[DepositOffer] = []
        for match in pair_pattern.finditer(block):
            term_months = int(match.group("term"))
            product_name = products.get(term_months)
            if not product_name:
                continue
            rate = extract_rate_percent(match.group("rate"))
            if rate is None:
                continue
            offers.append(
                self._make_offer(
                    product_name,
                    rate,
                    term_months,
                    maximum_deposit_amount=(
                        maximum_by_term.get(term_months) if maximum_by_term else None
                    ),
                )
            )
        return offers

    def _parse_rates_table(self, html: str) -> list[DepositOffer]:
        if is_bot_wall(html):
            return []

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)

        pln_section = re.search(
            r"Lokaty terminowe w PLN(.*?)(?:Lokaty terminowe w EUR|Konta oszczędnościowe w walutach|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not pln_section:
            return []

        section = pln_section.group(1)
        parts = re.split(r"Lokata terminowa Plus", section, maxsplit=1, flags=re.IGNORECASE)
        standard_section = parts[0]
        plus_section = parts[1] if len(parts) > 1 else ""

        offers: list[DepositOffer] = []
        offers.extend(self._parse_term_rate_block(standard_section, _STANDARD_PRODUCTS))
        offers.extend(
            self._parse_term_rate_block(
                plus_section,
                _PLUS_PRODUCTS,
                maximum_by_term={6: 50_000, 12: 100_000},
            )
        )
        return self._dedupe(offers)

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

        if not offers:
            text = soup.get_text("\n", strip=True)
            pln_block = re.search(
                r"Lokaty terminowe w PLN\s*\n(.*?)(?:\n##|\nLokaty terminowe w EUR|$)",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if pln_block:
                offers.extend(self._extract_from_text(pln_block.group(1)))

        return offers

    def _extract_from_section(self, section) -> list[DepositOffer]:
        return self._extract_from_text(section.get_text("\n", strip=True))

    def _extract_from_text(self, text: str) -> list[DepositOffer]:
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
            offers.append(self._make_offer(product_name, rate, term_months))

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
            offers.append(self._make_offer(product_name, rate, term_months))
        return self._dedupe(offers)

    def _make_offer(
        self,
        product_name: str,
        rate: float,
        term_months: int,
        maximum_deposit_amount: float | None = None,
    ) -> DepositOffer:
        return DepositOffer(
            institution_name=self.institution_name,
            product_name=product_name,
            annual_interest_rate=rate,
            term_months=term_months,
            source_url=ING_RATES_PDF_URL,
            bank_slug=self.bank_slug,
            interest_capitalization=InterestCapitalization.AT_MATURITY,
            minimum_deposit_amount=1000,
            maximum_deposit_amount=maximum_deposit_amount,
        )

    def _dedupe(self, offers: list[DepositOffer]) -> list[DepositOffer]:
        seen: set[str] = set()
        unique: list[DepositOffer] = []
        for offer in offers:
            if offer.external_id in seen:
                continue
            seen.add(offer.external_id)
            unique.append(offer)
        return unique
