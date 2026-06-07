import re
from decimal import Decimal, InvalidOperation


_RATE_PATTERN = re.compile(
    r"(\d+[.,]?\d*)\s*%?",
    re.IGNORECASE,
)


def parse_rate(raw: str) -> Decimal | None:
    """Normalize rate strings like 'do 6,5%', '6.5 percent annually' → 6.5."""
    if not raw:
        return None

    normalized = raw.strip().lower()
    normalized = normalized.replace(",", ".")

    match = _RATE_PATTERN.search(normalized)
    if not match:
        return None

    try:
        value = Decimal(match.group(1))
    except InvalidOperation:
        return None

    if value > 100:
        return None

    return value


def parse_term_months(raw: str) -> int | None:
    """Extract term in months from strings like '12 mies.', '1 rok', '3 lata'."""
    if not raw:
        return None

    text = raw.strip().lower().replace(",", ".")

    month_match = re.search(r"(\d+)\s*mies", text)
    if month_match:
        return int(month_match.group(1))

    year_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:rok|lat|year)", text)
    if year_match:
        years = float(year_match.group(1))
        return int(years * 12)

    return None


def parse_amount(raw: str) -> Decimal | None:
    """Parse monetary amounts like '1 000 zł', '10 000 PLN'."""
    if not raw:
        return None

    cleaned = re.sub(r"[^\d.,]", "", raw.replace(" ", "")).replace(",", ".")
    if not cleaned:
        return None

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
