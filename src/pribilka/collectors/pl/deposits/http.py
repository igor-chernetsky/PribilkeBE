import httpx

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PribilkaBot/1.0; +https://github.com/igor-chernetsky/PribilkeBE)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json",
    "Accept-Language": "pl-PL,pl;q=0.9",
}


def fetch_text(url: str, timeout: float = 30.0) -> str:
    response = httpx.get(url, headers=DEFAULT_HEADERS, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.text


def fetch_json(url: str, timeout: float = 30.0) -> object:
    response = httpx.get(
        url,
        headers={**DEFAULT_HEADERS, "Accept": "application/json"},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.json()
