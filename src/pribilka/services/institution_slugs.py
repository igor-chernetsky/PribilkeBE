"""Resolve stable institution slugs for branding in API responses."""

from __future__ import annotations

import re

_NAME_PATTERNS: tuple[tuple[str, str], ...] = (
    ("ing", r"\bing\b"),
    ("mbank", r"\bmbank\b|\bm bank\b"),
    ("pko", r"\bpko\b"),
    ("santander", r"\bsantander\b"),
    ("velobank", r"\bvelobank\b|\bvelo\b"),
    ("alior", r"\balior\b"),
    ("pekao", r"\bpekao\b"),
    ("millennium", r"\bmillennium\b"),
    ("raiffeisen", r"\braiffeisen\b"),
    ("unicredit", r"\bunicredit\b"),
    ("citi", r"\bciti\b"),
    ("credit-agricole", r"\bcredit\s*agricole\b|\bnoble\s+bank\b"),
    ("bos", r"\bbos\b|\bbank\s+ochrony\s+środowiska\b"),
    ("bankier", r"\bbankier\b"),
)


def normalize_bank_slug(raw: str | None) -> str | None:
    if not raw:
        return None
    slug = raw.strip().lower()
    if slug.startswith("bankier-"):
        slug = slug.removeprefix("bankier-")
    slug = re.sub(r"[^a-z0-9-]+", "-", slug).strip("-")
    return slug or None


def infer_bank_slug(institution_name: str) -> str | None:
    lowered = institution_name.lower()
    for slug, pattern in _NAME_PATTERNS:
        if re.search(pattern, lowered):
            return slug
    return None


def resolve_bank_slug(institution_name: str, bank_slug: str | None = None) -> str | None:
    normalized = normalize_bank_slug(bank_slug)
    if normalized:
        return normalized
    return infer_bank_slug(institution_name)
