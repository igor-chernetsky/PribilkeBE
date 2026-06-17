from uuid import uuid4

from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode, InterestCapitalization, RiskLevel
from pribilka.schemas.common import DepositResponse
from pribilka.services.ai_insights import _build_deposit_insight


def test_build_deposit_insight_above_market_average():
    deposit = DepositResponse(
        id=uuid4(),
        instrument_id=uuid4(),
        institution_name="mBank",
        product_name="Lokata 6M",
        annual_interest_rate=6.8,
        term_months=6,
        interest_capitalization=InterestCapitalization.AT_MATURITY,
        minimum_deposit_amount=1000.0,
        maximum_deposit_amount=None,
        early_withdrawal_conditions=None,
        promotional_rate_requirements=None,
        country=CountryCode.PL,
        currency=CurrencyCode.PLN,
        opportunity_score=86.5,
        risk_level=RiskLevel.LOW,
        last_collected_at=None,
    )

    insight = _build_deposit_insight(deposit, market_avg=6.3)

    assert insight.asset_class == AssetClass.BANK_DEPOSIT
    assert insight.source == "rules"
    assert "6.80%" in insight.summary
    assert any("above" in h for h in insight.highlights)
