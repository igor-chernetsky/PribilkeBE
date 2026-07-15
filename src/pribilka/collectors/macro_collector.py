"""Macro indicator collectors — NBP reference rate + Eurostat HICP (CPI YoY)."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx

from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.models.enums import AssetClass, CountryCode, MacroIndicatorKind

logger = logging.getLogger(__name__)

NBP_RATES_XML_URL = "https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml"
EUROSTAT_HICP_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_manr"
)

DEFAULT_HEADERS = {
    "User-Agent": "ZyskRadar/1.0 (+https://pribilka.webredirect.org)",
    "Accept": "application/xml,application/json,text/xml,*/*",
}


def _parse_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    text = raw.strip().replace(",", ".").replace("%", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def parse_nbp_reference_rates_xml(xml_text: str) -> list[dict]:
    """Parse NBP archival interest-rate XML into reference-rate rows."""
    # Skip BOM / junk before the root element.
    start = xml_text.find("<")
    if start > 0:
        xml_text = xml_text[start:]

    root = ET.fromstring(xml_text)
    rows: list[dict] = []

    for entry in root.iter():
        tag = entry.tag.lower().split("}")[-1]
        if tag not in {"pozycja", "entry", "item", "row"}:
            # Some archives nest rate fields directly under date-bearing nodes.
            pass

    # Prefer explicit <pozycja> / <pozycje>/<pozycja> layout used by NBP.
    candidates = list(root.findall(".//pozycja"))
    if not candidates:
        candidates = [node for node in root.iter() if node is not root]

    for node in candidates:
        attrs = {k.lower(): v for k, v in node.attrib.items()}
        children = {
            (child.tag.lower().split("}")[-1]): (child.text or "").strip()
            for child in list(node)
        }

        as_of_raw = (
            attrs.get("obowiazuje_od")
            or attrs.get("od")
            or attrs.get("effectivedate")
            or children.get("obowiazuje_od")
            or children.get("data")
            or children.get("date")
        )
        rate_raw = (
            attrs.get("ref")
            or children.get("ref")
            or children.get("reference_rate")
            or children.get("stopa_referencyjna")
        )
        # Nested layout: <pozycja><stopa id="ref" oprocentowanie="5.25"/></pozycja>
        if rate_raw is None:
            for child in list(node):
                child_tag = child.tag.lower().split("}")[-1]
                if child_tag != "stopa":
                    continue
                child_attrs = {k.lower(): v for k, v in child.attrib.items()}
                stopa_id = (child_attrs.get("id") or child_attrs.get("typ") or "").lower()
                if stopa_id in {"ref", "referencyjna", "reference"}:
                    rate_raw = child_attrs.get("oprocentowanie") or (child.text or "").strip()
                    break
        if not as_of_raw or rate_raw is None:
            continue

        as_of = _parse_date(as_of_raw)
        rate = _parse_decimal(rate_raw)
        if as_of is None or rate is None:
            continue

        rows.append(
            {
                "kind": MacroIndicatorKind.NBP_REFERENCE_RATE,
                "value": float(rate),
                "as_of_date": as_of,
                "source_name": "nbp_interest_rates",
                "source_url": NBP_RATES_XML_URL,
                "country": CountryCode.PL,
            }
        )

    # Deduplicate by date, keep last occurrence (chronological archive).
    by_date: dict[date, dict] = {}
    for row in rows:
        by_date[row["as_of_date"]] = row
    return [by_date[key] for key in sorted(by_date)]


def _parse_date(raw: str) -> date | None:
    text = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def parse_eurostat_hicp_json(payload: dict) -> list[dict]:
    """Parse Eurostat JSON-stat HICP YoY into monthly CPI rows for Poland."""
    value_map = payload.get("value") or {}
    dimension = payload.get("dimension") or {}
    time_dim = dimension.get("time") or {}
    time_index = (time_dim.get("category") or {}).get("index") or {}
    if not isinstance(time_index, dict) or not value_map:
        return []

    # Category index: {"2024-01": 0, ...} — invert to position -> period.
    position_to_period = {int(pos): period for period, pos in time_index.items()}
    rows: list[dict] = []
    for pos_str, raw_value in value_map.items():
        try:
            pos = int(pos_str)
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        period = position_to_period.get(pos)
        as_of = _period_to_month_end(period)
        if as_of is None:
            continue
        rows.append(
            {
                "kind": MacroIndicatorKind.CPI_YOY,
                "value": value,
                "as_of_date": as_of,
                "source_name": "eurostat_hicp",
                "source_url": EUROSTAT_HICP_URL,
                "country": CountryCode.PL,
            }
        )

    by_date: dict[date, dict] = {}
    for row in sorted(rows, key=lambda item: item["as_of_date"]):
        by_date[row["as_of_date"]] = row
    return [by_date[key] for key in sorted(by_date)]


def _period_to_month_end(period: str | None) -> date | None:
    if not period:
        return None
    # Eurostat monthly: "2024-01"
    match = re.fullmatch(r"(\d{4})-(\d{2})", period)
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


class PolandMacroCollector(BaseCollector):
    """Collects NBP reference rate + Eurostat HICP YoY for Poland."""

    def __init__(self):
        super().__init__(
            CollectorConfig(
                asset_class=AssetClass.BANK_DEPOSIT,
                country=CountryCode.PL,
                source_name="poland_macro",
                refresh_interval=timedelta(hours=24),
            )
        )

    def collect(self) -> list[dict]:
        records: list[dict] = []
        try:
            records.extend(self._collect_nbp_reference_rates())
        except Exception:
            logger.exception("NBP reference rate collect failed")
        try:
            records.extend(self._collect_eurostat_cpi())
        except Exception:
            logger.exception("Eurostat CPI collect failed")
        return records

    def _collect_nbp_reference_rates(self) -> list[dict]:
        response = httpx.get(NBP_RATES_XML_URL, headers=DEFAULT_HEADERS, timeout=60.0)
        response.raise_for_status()
        rows = parse_nbp_reference_rates_xml(response.text)
        logger.info("NBP reference rates parsed: %d rows", len(rows))
        return rows

    def _collect_eurostat_cpi(self) -> list[dict]:
        params = {
            "format": "JSON",
            "lang": "en",
            "geo": "PL",
            "coicop": "CP00",
            "lastTimePeriod": "36",
        }
        response = httpx.get(
            EUROSTAT_HICP_URL,
            params=params,
            headers={**DEFAULT_HEADERS, "Accept": "application/json"},
            timeout=60.0,
        )
        response.raise_for_status()
        rows = parse_eurostat_hicp_json(response.json())
        logger.info("Eurostat CPI YoY parsed: %d rows", len(rows))
        return rows
