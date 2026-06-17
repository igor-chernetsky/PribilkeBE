from pribilka.models.enums import AssetClass, RiskLevel
from pribilka.services.risk_levels import resolve_risk_level


def test_corporate_bond_is_high_risk():
    assert (
        resolve_risk_level(AssetClass.CORPORATE_BOND, opportunity_score=90.0, is_government=False)
        == RiskLevel.HIGH
    )


def test_government_bond_is_low_risk():
    assert (
        resolve_risk_level(AssetClass.GOVERNMENT_BOND, opportunity_score=10.0, is_government=True)
        == RiskLevel.LOW
    )


def test_deposit_risk_from_score():
    assert resolve_risk_level(AssetClass.BANK_DEPOSIT, 75.0, term_months=12) == RiskLevel.LOW
    assert resolve_risk_level(AssetClass.BANK_DEPOSIT, 60.0, term_months=12) == RiskLevel.MEDIUM
    assert resolve_risk_level(AssetClass.BANK_DEPOSIT, 45.0, term_months=12) == RiskLevel.HIGH


def test_long_deposit_term_bumps_risk():
    assert resolve_risk_level(AssetClass.BANK_DEPOSIT, 75.0, term_months=40) == RiskLevel.MEDIUM
    assert resolve_risk_level(AssetClass.BANK_DEPOSIT, 60.0, term_months=60) == RiskLevel.HIGH
