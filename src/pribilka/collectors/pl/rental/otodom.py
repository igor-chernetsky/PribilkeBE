from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from pribilka.collectors.pl.deposits.http import DEFAULT_HEADERS, is_bot_wall
from pribilka.collectors.pl.rental.cities import OTODOM_ROOM_PARAM
from pribilka.models.enums import RentalListingType

logger = logging.getLogger(__name__)

OTODOM_BASE = "https://www.otodom.pl"
OTODOM_HEADERS = {
    **DEFAULT_HEADERS,
    "Referer": f"{OTODOM_BASE}/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}
SEGMENT_REQUEST_DELAY_SEC = 2.0
RETRYABLE_STATUS_CODES = frozenset({403, 429, 502, 503, 504})
RETRY_BACKOFF_SEC = (4.0, 10.0, 25.0)
ROOMS_NUMBER_PATTERN = re.compile(r'"roomsNumber"\s*:\s*"([A-Z_]+)"')
PRICE_VALUE_PATTERN = re.compile(r'"value"\s*:\s*(\d+(?:\.\d+)?)\s*,\s*"currency"\s*:\s*"PLN"')
AREA_PATTERN = re.compile(r'"areaInSquareMeters"\s*:\s*(\d+(?:\.\d+)?)')
ID_PATTERN = re.compile(r'"id"\s*:\s*"?(\d+)"?')
SLUG_PATTERN = re.compile(r'"slug"\s*:\s*"([^"]+)"')
DATE_CREATED_PATTERN = re.compile(r'"dateCreated"\s*:\s*"([^"]+)"')
BUILD_ID_PATTERN = re.compile(r"/_next/static/([^/]+)/")


def build_otodom_search_url(
    *,
    location_path: str,
    listing_type: RentalListingType,
    room_count: int,
    page: int = 1,
    limit: int = 36,
) -> str:
    transaction = "sprzedaz" if listing_type == RentalListingType.SALE else "wynajem"
    room_token = OTODOM_ROOM_PARAM[room_count]
    rooms_query = quote(f"[{room_token}]")
    return (
        f"{OTODOM_BASE}/pl/wyniki/{transaction}/mieszkanie/{location_path}"
        f"?roomsNumber={rooms_query}&limit={limit}&page={page}"
    )


def create_otodom_client(*, timeout: float = 25.0) -> httpx.Client:
    return httpx.Client(headers=OTODOM_HEADERS, follow_redirects=True, timeout=timeout)


def fetch_otodom_search_html(url: str, *, timeout: float = 25.0, client: httpx.Client | None = None) -> str:
    if client is None:
        with create_otodom_client(timeout=timeout) as owned_client:
            warm_otodom_session(owned_client)
            return _get_with_retry(owned_client, url).text
    return _get_with_retry(client, url).text


def fetch_otodom_search_items(
    url: str,
    *,
    city_slug: str,
    listing_type: RentalListingType,
    room_count: int,
    timeout: float = 25.0,
    source: str = "otodom",
    client: httpx.Client | None = None,
) -> tuple[list[dict], str]:
    """Fetch a search page and parse listings, with JSON API fallback."""
    if client is None:
        with create_otodom_client(timeout=timeout) as owned_client:
            warm_otodom_session(owned_client)
            return _fetch_otodom_search_items_with_client(
                owned_client,
                url,
                city_slug=city_slug,
                listing_type=listing_type,
                room_count=room_count,
                source=source,
            )

    return _fetch_otodom_search_items_with_client(
        client,
        url,
        city_slug=city_slug,
        listing_type=listing_type,
        room_count=room_count,
        source=source,
    )


def _fetch_otodom_search_items_with_client(
    client: httpx.Client,
    url: str,
    *,
    city_slug: str,
    listing_type: RentalListingType,
    room_count: int,
    source: str,
) -> tuple[list[dict], str]:
    response = _get_with_retry(client, url)
    html = response.text

    listings = parse_otodom_search_html(
        html,
        city_slug=city_slug,
        listing_type=listing_type,
        room_count=room_count,
        source=source,
    )
    if listings:
        return listings, html

    next_data = _extract_next_data(html)
    build_id = _extract_build_id(next_data, html)
    if build_id:
        json_items = _fetch_search_items_via_next_json(client, url, build_id)
        if json_items:
            listings = _normalize_listings(
                json_items,
                city_slug=city_slug,
                listing_type=listing_type,
                room_count=room_count,
                source=source,
            )
            if listings:
                logger.info("Otodom JSON API fallback returned %d listings for %s", len(listings), city_slug)
                return listings, html

    return listings, html


def _get_with_retry(client: httpx.Client, url: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
    request_headers = headers or OTODOM_HEADERS
    last_error: Exception | None = None

    for attempt in range(len(RETRY_BACKOFF_SEC) + 1):
        if attempt:
            time.sleep(RETRY_BACKOFF_SEC[attempt - 1])
        try:
            response = client.get(url, headers=request_headers)
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < len(RETRY_BACKOFF_SEC):
                logger.warning(
                    "Otodom HTTP %s for %s, retry %d/%d",
                    response.status_code,
                    url,
                    attempt + 1,
                    len(RETRY_BACKOFF_SEC),
                )
                continue
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code in RETRYABLE_STATUS_CODES and attempt < len(RETRY_BACKOFF_SEC):
                continue
            raise

    if last_error:
        raise last_error
    raise RuntimeError(f"Otodom request failed for {url}")


def warm_otodom_session(client: httpx.Client) -> None:
    try:
        client.get(
            f"{OTODOM_BASE}/",
            headers={**OTODOM_HEADERS, "Sec-Fetch-Site": "none"},
        )
    except Exception:
        logger.warning("Otodom session warm-up failed", exc_info=True)


def parse_otodom_search_html(
    html: str,
    *,
    city_slug: str,
    listing_type: RentalListingType,
    room_count: int,
    source: str = "otodom",
) -> list[dict]:
    if is_bot_wall(html):
        logger.warning("Otodom bot wall detected for %s", city_slug)
        return []

    listings: list[dict] = []
    seen: set[str] = set()

    next_data = _extract_next_data(html)
    if next_data is not None:
        for item in _extract_search_ads_items(next_data):
            record = _normalize_listing(
                item,
                city_slug=city_slug,
                listing_type=listing_type,
                room_count=room_count,
                source=source,
            )
            if record and record["external_id"] not in seen:
                seen.add(record["external_id"])
                listings.append(record)
        if listings:
            return listings

    payloads: list[Any] = []
    if next_data is not None:
        payloads.append(next_data)

    payloads.extend(_extract_json_objects(html))

    for payload in payloads:
        for item in _walk_listing_candidates(payload):
            record = _normalize_listing(
                item,
                city_slug=city_slug,
                listing_type=listing_type,
                room_count=room_count,
                source=source,
            )
            if record and record["external_id"] not in seen:
                seen.add(record["external_id"])
                listings.append(record)

    if not listings:
        listings = _parse_regex_fallback(
            html,
            city_slug=city_slug,
            listing_type=listing_type,
            room_count=room_count,
            source=source,
        )

    return listings


def _extract_search_ads_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    try:
        items = payload["props"]["pageProps"]["data"]["searchAds"]["items"]
    except (KeyError, TypeError):
        return []
    return items if isinstance(items, list) else []


def _extract_build_id(next_data: Any | None, html: str) -> str | None:
    if isinstance(next_data, dict):
        build_id = next_data.get("buildId")
        if isinstance(build_id, str) and build_id:
            return build_id
    match = BUILD_ID_PATTERN.search(html)
    return match.group(1) if match else None


def _fetch_search_items_via_next_json(
    client: httpx.Client,
    url: str,
    build_id: str,
) -> list[dict[str, Any]]:
    parsed = urlparse(url)
    json_url = f"{OTODOM_BASE}/_next/data/{build_id}{parsed.path}.json"
    if parsed.query:
        json_url = f"{json_url}?{parsed.query}"

    response = _get_with_retry(
        client,
        json_url,
        headers={
            **OTODOM_HEADERS,
            "Accept": "application/json",
            "x-nextjs-data": "1",
        },
    )
    payload = response.json()
    return _extract_search_ads_items({"props": {"pageProps": payload.get("pageProps", {})}})


def _normalize_listings(
    items: list[dict[str, Any]],
    *,
    city_slug: str,
    listing_type: RentalListingType,
    room_count: int,
    source: str,
) -> list[dict]:
    listings: list[dict] = []
    seen: set[str] = set()
    for item in items:
        record = _normalize_listing(
            item,
            city_slug=city_slug,
            listing_type=listing_type,
            room_count=room_count,
            source=source,
        )
        if record and record["external_id"] not in seen:
            seen.add(record["external_id"])
            listings.append(record)
    return listings


def _extract_next_data(html: str) -> Any | None:
    match = re.search(
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(?P<payload>.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(match.group("payload"))
    except json.JSONDecodeError:
        return None


def _extract_json_objects(html: str) -> list[Any]:
    objects: list[Any] = []
    for match in re.finditer(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            objects.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    return objects


def _walk_listing_candidates(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(value: Any, depth: int = 0) -> None:
        if depth > 12:
            return
        if isinstance(value, dict):
            if _looks_like_listing(value):
                found.append(value)
                return
            for child in value.values():
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                walk(child, depth + 1)

    walk(node)
    return found


def _looks_like_listing(value: dict[str, Any]) -> bool:
    has_id = any(key in value for key in ("id", "adId", "listingId", "publicId"))
    has_price = any(
        key in value for key in ("totalPrice", "price", "rentPrice", "priceExact")
    )
    return bool(has_id and has_price)


def _normalize_listing(
    item: dict[str, Any],
    *,
    city_slug: str,
    listing_type: RentalListingType,
    room_count: int,
    source: str,
) -> dict | None:
    external_id = str(
        item.get("id")
        or item.get("adId")
        or item.get("listingId")
        or item.get("publicId")
        or ""
    ).strip()
    if not external_id:
        return None

    price = _extract_price(item)
    if price is None or price <= 0:
        return None

    area = _extract_area(item)
    slug = item.get("slug")
    href = item.get("href")
    if isinstance(href, str) and href.startswith("/"):
        url = f"{OTODOM_BASE}{href}"
    elif slug:
        url = f"{OTODOM_BASE}/pl/oferta/{slug}"
    else:
        url = item.get("canonicalUrl")
    published_at = _parse_datetime(item.get("dateCreated") or item.get("createdAt"))

    return {
        "source": source,
        "external_id": external_id,
        "listing_type": listing_type,
        "city_slug": city_slug,
        "room_count": room_count,
        "price_pln": price,
        "area_sqm": area,
        "price_per_sqm": round(price / area, 2) if area and area > 0 else None,
        "title": item.get("title") or item.get("name"),
        "url": url,
        "published_at": published_at,
    }


def _extract_price(item: dict[str, Any]) -> float | None:
    if item.get("priceExact") is not None:
        return float(item["priceExact"])
    for key in ("totalPrice", "price", "rentPrice"):
        raw = item.get(key)
        if isinstance(raw, dict):
            value = raw.get("value")
            if value is not None:
                return float(value)
        elif raw is not None:
            return float(raw)
    return None


def _extract_area(item: dict[str, Any]) -> float | None:
    for key in ("areaInSquareMeters", "areaSqm", "area"):
        raw = item.get(key)
        if raw is None:
            continue
        if isinstance(raw, dict):
            value = raw.get("value") or raw.get("size")
            if value is not None:
                return float(value)
        else:
            return float(raw)
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _parse_regex_fallback(
    html: str,
    *,
    city_slug: str,
    listing_type: RentalListingType,
    room_count: int,
    source: str,
) -> list[dict]:
    ids = ID_PATTERN.findall(html)
    prices = [float(v) for v in PRICE_VALUE_PATTERN.findall(html)]
    areas = [float(v) for v in AREA_PATTERN.findall(html)]
    slugs = SLUG_PATTERN.findall(html)
    dates = DATE_CREATED_PATTERN.findall(html)

    records: list[dict] = []
    for index, external_id in enumerate(ids):
        if index >= len(prices):
            break
        price = prices[index]
        area = areas[index] if index < len(areas) else None
        slug = slugs[index] if index < len(slugs) else None
        published_at = _parse_datetime(dates[index]) if index < len(dates) else None
        records.append(
            {
                "source": source,
                "external_id": external_id,
                "listing_type": listing_type,
                "city_slug": city_slug,
                "room_count": room_count,
                "price_pln": price,
                "area_sqm": area,
                "price_per_sqm": round(price / area, 2) if area and area > 0 else None,
                "title": None,
                "url": f"{OTODOM_BASE}/pl/oferta/{slug}" if slug else None,
                "published_at": published_at,
            }
        )
    return records
