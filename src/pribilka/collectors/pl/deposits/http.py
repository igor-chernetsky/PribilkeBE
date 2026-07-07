import io
import logging
import time

import httpx

logger = logging.getLogger(__name__)

# Avoid "br" in Accept-Encoding — some Polish bank CDNs return a stripped SPA shell
# when Brotli is advertised but not decoded correctly by the client stack.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
}

# ING fileserver serves the real rate PDF to Googlebot while Imperva blocks browsers.
GOOGLEBOT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Accept": "application/pdf,*/*",
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


def fetch_text(
    url: str,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> str:
    response = _request_with_retry(
        url=url,
        timeout=timeout,
        headers=headers or DEFAULT_HEADERS,
    )
    response.raise_for_status()
    return response.text


def fetch_bytes(
    url: str,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> bytes:
    response = _request_with_retry(
        url=url,
        timeout=timeout,
        headers=headers or DEFAULT_HEADERS,
    )
    response.raise_for_status()
    return response.content


def fetch_json(
    url: str,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> object:
    response = _request_with_retry(
        url=url,
        timeout=timeout,
        headers={
            **(headers or DEFAULT_HEADERS),
            "Accept": "application/json",
        },
    )
    response.raise_for_status()
    return response.json()


def _request_with_retry(
    *,
    url: str,
    timeout: float,
    headers: dict[str, str],
    max_attempts: int = 3,
    base_delay_seconds: float = 1.2,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = httpx.get(
                url,
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status = exc.response.status_code
            if status not in {408, 425, 429, 500, 502, 503, 504} or attempt == max_attempts:
                raise
            delay = base_delay_seconds * attempt
            logger.warning(
                "Retrying %s after HTTP %s (attempt %d/%d, sleep %.1fs)",
                url,
                status,
                attempt,
                max_attempts,
                delay,
            )
            time.sleep(delay)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt == max_attempts:
                raise
            delay = base_delay_seconds * attempt
            logger.warning(
                "Retrying %s after network error %s (attempt %d/%d, sleep %.1fs)",
                url,
                type(exc).__name__,
                attempt,
                max_attempts,
                delay,
            )
            time.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Unexpected retry loop state")


def extract_pdf_text(content: bytes) -> str:
    """Extract text from a PDF byte stream."""
    if not content.startswith(b"%PDF"):
        return ""

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        logger.exception("Failed to extract PDF text")
        return ""
