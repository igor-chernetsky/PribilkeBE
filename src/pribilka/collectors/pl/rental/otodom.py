from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from pribilka.collectors.pl.deposits.http import DEFAULT_HEADERS, is_bot_wall
from pribilka.collectors.pl.rental.cities import OTODOM_ROOM_PARAM
from pribilka.models.enums import RentalListingType

logger = logging.getLogger(__name__)

OTODOM_BASE = "https://www.otodom.pl"
ROOMS_NUMBER_PATTERN = re.compile(r'"roomsNumber"\s*:\s*"([A-Z_]+)"')
PRICE_VALUE_PATTERN = re.compile(r'"value"\s*:\s*(\d+(?:\.\d+)?)\s*,\s*"currency"\s*:\s*"PLN"')
AREA_PATTERN = re.compile(r'"areaInSquareMeters"\s*:\s*(\d+(?:\.\d+)?)')
ID_PATTERN = re.compile(r'"id"\s*:\s*"?(\d+)"?')
SLUG_PATTERN = re.compile(r'"slug"\s*:\s*"([^"]+)"')
DATE_CREATED_PATTERN = re.compile(r'"dateCreated"\s*:\s*"([^"]+)"')


def build_otodom_search_url(
    *,
    city_slug: str,
    listing_type: RentalListingType,
    room_count: int,
    page: int = 1,
    limit: int = 36,
) -> str:
    transaction = "sprzedaz" if listing_type == RentalListingType.SALE else "wynajem"
    room_token = OTODOM_ROOM_PARAM[room_count]
    rooms_query = quote(f"[{room_token}]")
    return (
        f"{OTODOM_BASE}/pl/wyniki/{transaction}/mieszkanie/{city_slug}"
        f"?roomsNumber={rooms_query}&limit={limit}&page={page}"
    )


def fetch_otodom_search_html(url: str, *, timeout: float = 25.0) -> str:
    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


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

    payloads: list[Any] = []
    next_data = _extract_next_data(html)
    if next_data is not None:
        payloads.append(next_data)

    payloads.extend(_extract_json_objects(html))
    listings: list[dict] = []
    seen: set[str] = set()

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
    has_id = "id" in value or "adId" in value
    has_price = any(key in value for key in ("totalPrice", "price", "rentPrice"))
    has_area = any(key in value for key in ("areaInSquareMeters", "area"))
    return bool(has_id and has_price and has_area)


def _normalize_listing(
    item: dict[str, Any],
    *,
    city_slug: str,
    listing_type: RentalListingType,
    room_count: int,
    source: str,
) -> dict | None:
    external_id = str(item.get("id") or item.get("adId") or "").strip()
    if not external_id:
        return None

    price = _extract_price(item)
    if price is None or price <= 0:
        return None

    area = _extract_area(item)
    slug = item.get("slug")
    url = f"{OTODOM_BASE}/pl/oferta/{slug}" if slug else None
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
    for key in ("areaInSquareMeters", "area"):
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
