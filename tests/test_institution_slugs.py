from pribilka.services.institution_slugs import (
    infer_bank_slug,
    normalize_bank_slug,
    resolve_bank_slug,
)


def test_normalize_bankier_prefix():
    assert normalize_bank_slug("bankier-mbank") == "mbank"


def test_infer_from_institution_name():
    assert infer_bank_slug("ING Bank Śląski") == "ing"
    assert infer_bank_slug("mBank") == "mbank"


def test_resolve_prefers_explicit_slug():
    assert resolve_bank_slug("Unknown", "velobank") == "velobank"
