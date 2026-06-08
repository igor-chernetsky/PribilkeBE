import re
from decimal import Decimal

from pribilka.services.normalization import parse_rate, parse_term_months

_TERM_IN_NAME = re.compile(r"(\d+)\s*m(?:ies)?", re.IGNORECASE)


def extract_rate_percent(text: str) -> float | None:
    rate = parse_rate(text)
    return float(rate) if rate is not None else None


def extract_term_from_text(text: str) -> int | None:
    term = parse_term_months(text)
    if term:
        return term

    match = _TERM_IN_NAME.search(text)
    if match:
        return int(match.group(1))

    year_match = re.search(r"(\d+)\s*(?:rok|lat)", text, re.IGNORECASE)
    if year_match:
        return int(year_match.group(1)) * 12

    return None


def find_product_rate_pairs(html: str, pattern: str) -> list[tuple[str, float]]:
    """Extract (product_name, rate) tuples using regex with named groups."""
    results = []
    for match in re.finditer(pattern, html, re.IGNORECASE | re.DOTALL):
        name = match.group("name").strip()
        rate = extract_rate_percent(match.group("rate"))
        if rate is not None:
            results.append((name, rate))
    return results


def decimal_rate(value: float) -> Decimal:
    return Decimal(str(value))
