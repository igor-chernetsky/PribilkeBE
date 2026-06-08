"""Parser for retail government savings bonds (obligacje skarbowe)."""

import re
from datetime import date

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


class ObligacjeSkarboweParser:
    source_name = "obligacje_skarbowe_scraper"

    def parse(self) -> list[dict]:
        html = fetch_text(OBLIGACJE_URL)
        return self._parse_html(html)

    def _parse_html(self, html: str) -> list[dict]:
        pattern = re.compile(
            r"(?P<rate>\d+[,.]\d+)%[^\(]*\(symbol:\s*(?P<series>[A-Z]{3})\)",
            re.IGNORECASE,
        )

        records: list[dict] = []
        seen: set[str] = set()

        for match in pattern.finditer(html):
            series = match.group("series").upper()
            if series not in SERIES_TERM_MONTHS or series in seen:
                continue

            rate = float(match.group("rate").replace(",", "."))
            term_months = SERIES_TERM_MONTHS[series]
            maturity_date = date.today() + relativedelta(months=term_months)

            records.append(
                {
                    "external_id": f"pl-gov-{series.lower()}",
                    "is_government": True,
                    "issuer": "Ministerstwo Finansów RP",
                    "bond_series": series,
                    "isin": None,
                    "maturity_date": maturity_date,
                    "coupon_rate": rate,
                    "yield_to_maturity": rate,
                    "market_price": 100.0,
                    "currency": CurrencyCode.PLN,
                    "source_url": OBLIGACJE_URL,
                }
            )
            seen.add(series)

        return records
