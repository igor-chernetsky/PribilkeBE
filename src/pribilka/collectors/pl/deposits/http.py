import httpx

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def is_bot_wall(html: str) -> bool:
    """Detect WAF/bot challenge pages that contain no product data."""
    lowered = html.lower()
    if len(html) < 5_000 and (
        "incapsula" in lowered
        or "_incapsula_resource" in lowered
        or ("robots" in lowered and "noindex" in lowered and "iframe" in lowered)
    ):
        return True
    return False


def fetch_text(url: str, timeout: float = 30.0) -> str:
    response = httpx.get(url, headers=DEFAULT_HEADERS, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.text


def fetch_bytes(url: str, timeout: float = 30.0) -> bytes:
    response = httpx.get(url, headers=DEFAULT_HEADERS, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.content


def fetch_json(url: str, timeout: float = 30.0) -> object:
    response = httpx.get(
        url,
        headers={**DEFAULT_HEADERS, "Accept": "application/json"},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.json()
