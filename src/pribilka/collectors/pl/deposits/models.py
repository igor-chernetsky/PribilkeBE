import re
import unicodedata
from dataclasses import dataclass

from pribilka.models.enums import CountryCode, CurrencyCode, InterestCapitalization


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "product"


@dataclass
class DepositOffer:
    institution_name: str
    product_name: str
    annual_interest_rate: float
    term_months: int
    source_url: str
    bank_slug: str
    currency: CurrencyCode = CurrencyCode.PLN
    interest_capitalization: InterestCapitalization = InterestCapitalization.AT_MATURITY
    minimum_deposit_amount: float | None = None
    maximum_deposit_amount: float | None = None
    early_withdrawal_conditions: str | None = None
    promotional_rate_requirements: str | None = None

    @property
    def external_id(self) -> str:
        return f"{self.bank_slug}-{slugify(self.product_name)}-{self.term_months}m"

    def to_record(self, country: CountryCode, source_name: str) -> dict:
        return {
            "external_id": self.external_id,
            "institution_name": self.institution_name,
            "product_name": self.product_name,
            "annual_interest_rate": self.annual_interest_rate,
            "term_months": self.term_months,
            "interest_capitalization": self.interest_capitalization,
            "minimum_deposit_amount": self.minimum_deposit_amount,
            "maximum_deposit_amount": self.maximum_deposit_amount,
            "early_withdrawal_conditions": self.early_withdrawal_conditions,
            "promotional_rate_requirements": self.promotional_rate_requirements,
            "currency": self.currency,
            "country": country,
            "source_url": self.source_url,
            "source_name": source_name,
        }
