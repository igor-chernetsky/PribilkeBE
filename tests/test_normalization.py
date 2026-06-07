from decimal import Decimal

from pribilka.services.normalization import parse_amount, parse_rate, parse_term_months


def test_parse_rate_variants():
    assert parse_rate("do 6,5%") == Decimal("6.5")
    assert parse_rate("6.5 percent annually") == Decimal("6.5")
    assert parse_rate("annual yield 6.5%") == Decimal("6.5")


def test_parse_term_months():
    assert parse_term_months("12 mies.") == 12
    assert parse_term_months("1 rok") == 12
    assert parse_term_months("3 lata") == 36


def test_parse_amount():
    assert parse_amount("1 000 zł") == Decimal("1000")
    assert parse_amount("10 000 PLN") == Decimal("10000")
