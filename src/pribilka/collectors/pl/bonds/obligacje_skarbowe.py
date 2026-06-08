"""Parser for retail government savings bonds (obligacje skarbowe)."""

import re
from datetime import date

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta

from pribilka.collectors.pl.deposits.http import fetch_text
from pribilka.models.enums import CurrencyCode

OBLIGACJE_URL = "https://www.obligacjeskarbowe.pl/"

SERIES_TERM_MONTHS = {
    "OTS": 3,
    "ROR": 12,
    "DOR": 24,
    "TOS": 36,
    "COI": 48,
    "EDO": 120,
    "ROS": 72,
    "ROD": 144,
}

SERIES_NAMES = {
    "OTS": "Obligacja 3-miesięczna OTS",
    "ROR": "Obligacja roczna ROR",
    "DOR": "Obligacja 2-letnia DOR",
    "TOS": "Obligacja 3-letnia TOS",
    "COI": "Obligacja 4-letnia COI (indeksowana inflacją)",
    "EDO": "Obligacja 10-letnia EDO (indeksowana inflacją)",
    "ROS": "Rodzinna obligacja 6-letnia ROS",
    "ROD": "Rodzinna obligacja 12-letnia ROD",
}

_SYMBOL_PATTERN = re.compile(r"\(symbol:\s*(?P<series>[A-Z]{3})\s*\)", re.IGNORECASE)
_RATE_PATTERN = re.compile(r"(?P<rate>\d+[,.]\d+)\s*%")
_INLINE_PATTERN = re.compile(
    r"(?P<rate>\d+[,.]\d+)%[^\(]*\(symbol:\s*(?P<series>[A-Z]{3})\s*\)",
    re.IGNORECASE,
)


class ObligacjeSkarboweParser:
    source_name = "obligacje_skarbowe_scraper"

    def parse(self) -> list[dict]:
        html = fetch_text(OBLIGACJE_URL)
        return self._parse_html(html)

    def _parse_html(self, html: str) -> list[dict]:
        records = self._parse_product_cards(html)
        if len(records) < 4:
            records = self._parse_inline_text(html)
        return records

    def _parse_product_cards(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        records: list[dict] = []
        seen: set[str] = set()

        for card in soup.select("div.product-card"):
            card_text = card.get_text(" ", strip=True)
            symbol_match = _SYMBOL_PATTERN.search(card_text)
            if not symbol_match:
                continue

            series = symbol_match.group("series").upper()
            if series not in SERIES_TERM_MONTHS or series in seen:
                continue

            rate_match = _RATE_PATTERN.search(card_text)
            if not rate_match:
                continue

            records.append(self._build_record(series, rate_match.group("rate")))
            seen.add(series)

        return records

    def _parse_inline_text(self, html: str) -> list[dict]:
        """Fallback for compact HTML where rate and symbol sit on one line."""
        text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
        records: list[dict] = []
        seen: set[str] = set()

        for match in _INLINE_PATTERN.finditer(text):
            series = match.group("series").upper()
            if series not in SERIES_TERM_MONTHS or series in seen:
                continue
            records.append(self._build_record(series, match.group("rate")))
            seen.add(series)

        if records:
            return records

        # Last resort: pair symbol lines with nearest preceding rate line.
        lines = text.split("\n")
        pending_rate: str | None = None
        for line in lines:
            rate_match = _RATE_PATTERN.search(line)
            if rate_match and "symbol:" not in line.lower():
                pending_rate = rate_match.group("rate")

            symbol_match = _SYMBOL_PATTERN.search(line)
            if symbol_match and pending_rate:
                series = symbol_match.group("series").upper()
                if series in SERIES_TERM_MONTHS and series not in seen:
                    records.append(self._build_record(series, pending_rate))
                    seen.add(series)

        return records

    def _build_record(self, series: str, rate_raw: str) -> dict:
        rate = float(rate_raw.replace(",", "."))
        term_months = SERIES_TERM_MONTHS[series]
        return {
            "external_id": f"pl-gov-{series.lower()}",
            "is_government": True,
            "issuer": "Ministerstwo Finansów RP",
            "bond_series": series,
            "product_name": SERIES_NAMES.get(series, f"Obligacja {series}"),
            "isin": None,
            "maturity_date": date.today() + relativedelta(months=term_months),
            "coupon_rate": rate,
            "yield_to_maturity": rate,
            "market_price": 100.0,
            "currency": CurrencyCode.PLN,
            "source_url": OBLIGACJE_URL,
        }
