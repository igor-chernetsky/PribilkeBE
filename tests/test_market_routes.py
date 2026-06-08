import pytest
from fastapi import HTTPException

from pribilka.api.deps import parse_market_country
from pribilka.models.enums import CountryCode


def test_parse_market_country_lowercase():
    assert parse_market_country("pl") == CountryCode.PL


def test_parse_market_country_uppercase():
    assert parse_market_country("PL") == CountryCode.PL


def test_parse_market_country_unsupported():
    with pytest.raises(HTTPException) as exc:
        parse_market_country("xx")
    assert exc.value.status_code == 404
