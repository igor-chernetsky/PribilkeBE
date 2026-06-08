"""Bankier.pl SMART ranking — supplementary deposit source."""

import json
import re

from bs4 import BeautifulSoup

from pribilka.collectors.pl.deposits.base import BankDepositParser
from pribilka.collectors.pl.deposits.http import fetch_text
from pribilka.collectors.pl.deposits.models import DepositOffer, slugify
from pribilka.collectors.pl.deposits.utils import extract_rate_percent, extract_term_from_text

BANKIER_LOKATY_URL = "https://www.bankier.pl/smart/lokaty?depositAmount=10000&depositPeriod=0"

BANKIER_API_CANDIDATES = [
    "https://www.bankier.pl/core/DepositOffer/GetDepositOffers"
    "?depositAmount=10000&depositPeriod=0&page=1&pageSize=100",
    "https://www.bankier.pl/smart/api/deposit-offers?depositAmount=10000&page=1&pageSize=100",
]


class BankierDepositParser(BankDepositParser):
    institution_name = "Bankier.pl (ranking)"
    bank_slug = "bankier"
    source_name = "bankier_aggregator"

    def parse(self) -> list[DepositOffer]:
        offers = self._try_api_endpoints()
        if not offers:
            offers = self._parse_html(fetch_text(BANKIER_LOKATY_URL))
        return offers

    def _try_api_endpoints(self) -> list[DepositOffer]:
        from pribilka.collectors.pl.deposits.http import fetch_json

        for url in BANKIER_API_CANDIDATES:
            try:
                data = fetch_json(url)
            except Exception:
                continue
            offers = self._parse_api_payload(data)
            if offers:
                return offers
        return []

    def _parse_api_payload(self, data: object) -> list[DepositOffer]:
        if not isinstance(data, dict):
            return []

        items = data.get("items") or data.get("offers") or data.get("data") or []
        if not isinstance(items, list):
            return []

        offers: list[DepositOffer] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            offer = self._item_to_offer(item)
            if offer:
                offers.append(offer)
        return offers

    def _item_to_offer(self, item: dict) -> DepositOffer | None:
        product_name = (
            item.get("offerName")
            or item.get("productName")
            or item.get("name")
            or item.get("title")
        )
        bank_name = item.get("bankName") or item.get("institutionName") or item.get("bank")
        rate_raw = item.get("interestRate") or item.get("rate") or item.get("interest")
        term_raw = item.get("periodMonths") or item.get("period") or item.get("termMonths")

        if not product_name or rate_raw is None:
            return None

        rate = extract_rate_percent(str(rate_raw))
        if rate is None:
            return None

        term_months = int(term_raw) if term_raw else extract_term_from_text(str(product_name))
        if not term_months:
            return None

        institution = str(bank_name) if bank_name else self.institution_name
        bank_slug = slugify(institution)[:40]

        return DepositOffer(
            institution_name=institution,
            product_name=str(product_name).strip(),
            annual_interest_rate=rate,
            term_months=term_months,
            source_url=BANKIER_LOKATY_URL,
            bank_slug=f"bankier-{bank_slug}",
            minimum_deposit_amount=item.get("minAmount"),
            maximum_deposit_amount=item.get("maxAmount"),
            promotional_rate_requirements=(
                "Dodatkowe warunki" if item.get("hasAdditionalConditions") else None
            ),
        )

    def _parse_html(self, html: str) -> list[DepositOffer]:
        offers = self._parse_embedded_json(html)
        if offers:
            return offers

        text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
        offers = []

        product_pattern = re.compile(
            r"\n\d+\.\s*\n\s*(?P<name>.+?\(\d+\s*mies\.?\))\s*\n\s*Okres\s*\n\s*"
            r"(?P<term>\d+)\s*mies\.?\s*\n(?:.*?\n){0,8}?Oprocentowanie\s*\n\s*"
            r"(?P<rate>\d+(?:[,.]\d+)?)\s*%",
            re.IGNORECASE | re.DOTALL,
        )

        for match in product_pattern.finditer(text):
            product_name = re.sub(r"\s+", " ", match.group("name").strip())
            term_months = int(match.group("term"))
            rate = extract_rate_percent(match.group("rate"))
            if rate is None:
                continue

            institution = self._guess_institution(product_name)
            offers.append(
                DepositOffer(
                    institution_name=institution,
                    product_name=product_name,
                    annual_interest_rate=rate,
                    term_months=term_months,
                    source_url=BANKIER_LOKATY_URL,
                    bank_slug=f"bankier-{slugify(institution)[:30]}",
                    minimum_deposit_amount=1000,
                    promotional_rate_requirements="Źródło: ranking Bankier.pl",
                )
            )

        return self._dedupe(offers)

    def _parse_embedded_json(self, html: str) -> list[DepositOffer]:
        for raw in re.findall(
            r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE,
        ):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            offers = self._walk_json_for_offers(data)
            if offers:
                return offers

        next_data = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if next_data:
            try:
                data = json.loads(next_data.group(1))
                offers = self._walk_json_for_offers(data)
                if offers:
                    return offers
            except json.JSONDecodeError:
                pass

        return []

    def _walk_json_for_offers(self, node: object, depth: int = 0) -> list[DepositOffer]:
        if depth > 12:
            return []

        if isinstance(node, list):
            offers: list[DepositOffer] = []
            for item in node:
                if isinstance(item, dict) and self._looks_like_offer(item):
                    offer = self._item_to_offer(item)
                    if offer:
                        offers.append(offer)
                offers.extend(self._walk_json_for_offers(item, depth + 1))
            return offers

        if isinstance(node, dict):
            offers = []
            if self._looks_like_offer(node):
                offer = self._item_to_offer(node)
                if offer:
                    offers.append(offer)
            for value in node.values():
                offers.extend(self._walk_json_for_offers(value, depth + 1))
            return offers

        return []

    def _looks_like_offer(self, item: dict) -> bool:
        has_name = any(k in item for k in ("offerName", "productName", "name", "title"))
        has_rate = any(k in item for k in ("interestRate", "rate", "interest", "oprocentowanie"))
        return has_name and has_rate

    def _guess_institution(self, product_name: str) -> str:
        lowered = product_name.lower()
        mapping = {
            "velolokata": "VeloBank",
            "velo": "VeloBank",
            "pko": "PKO Bank Polski",
            "ing": "ING Bank Śląski",
            "mbank": "mBank",
            "santander": "Santander Bank Polska",
            "alior": "Alior Bank",
            "pekao": "Bank Pekao",
            "millennium": "Bank Millennium",
        }
        for key, name in mapping.items():
            if key in lowered:
                return name
        return "Bankier.pl (ranking)"

    def _dedupe(self, offers: list[DepositOffer]) -> list[DepositOffer]:
        seen: set[str] = set()
        unique: list[DepositOffer] = []
        for offer in offers:
            if offer.external_id in seen:
                continue
            seen.add(offer.external_id)
            unique.append(offer)
        return unique
