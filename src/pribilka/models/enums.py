import enum


class AssetClass(str, enum.Enum):
    BANK_DEPOSIT = "bank_deposit"
    GOVERNMENT_BOND = "government_bond"
    CORPORATE_BOND = "corporate_bond"
    GOLD = "gold"
    FOREIGN_EXCHANGE = "foreign_exchange"


class MacroIndicatorKind(str, enum.Enum):
    NBP_REFERENCE_RATE = "nbp_reference_rate"
    CPI_YOY = "cpi_yoy"


class CountryCode(str, enum.Enum):
    PL = "PL"
    DE = "DE"
    CZ = "CZ"
    SK = "SK"
    UA = "UA"


class CurrencyCode(str, enum.Enum):
    PLN = "PLN"
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"
    CHF = "CHF"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MarketEventType(str, enum.Enum):
    NEW_INSTRUMENT = "new_instrument"
    RATE_INCREASED = "rate_increased"
    RATE_DECREASED = "rate_decreased"
    YIELD_INCREASED = "yield_increased"
    YIELD_DECREASED = "yield_decreased"
    PRICE_CHANGED = "price_changed"
    MATURITY_APPROACHING = "maturity_approaching"
    INSTRUMENT_REMOVED = "instrument_removed"


class InterestCapitalization(str, enum.Enum):
    AT_MATURITY = "at_maturity"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    DAILY = "daily"


class RentalListingType(str, enum.Enum):
    SALE = "sale"
    RENT = "rent"
