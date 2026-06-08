from typing import Annotated

from fastapi import HTTPException, Path

from pribilka.models.enums import CountryCode

SUPPORTED_MARKETS = {c.value.lower(): c for c in CountryCode}


def parse_market_country(
    country: Annotated[
        str,
        Path(description="ISO 3166-1 alpha-2 market code", examples=["pl"], min_length=2, max_length=2),
    ],
) -> CountryCode:
    market = SUPPORTED_MARKETS.get(country.lower())
    if market is None:
        raise HTTPException(status_code=404, detail=f"Market '{country}' is not supported")
    return market
