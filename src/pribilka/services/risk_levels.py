from pribilka.models.enums import AssetClass, RiskLevel


def resolve_risk_level(
    asset_class: AssetClass,
    opportunity_score: float | None = None,
    *,
    term_months: int | None = None,
    is_government: bool | None = None,
) -> RiskLevel:
    if asset_class == AssetClass.GOVERNMENT_BOND or is_government is True:
        return RiskLevel.LOW
    if asset_class == AssetClass.CORPORATE_BOND or is_government is False:
        return RiskLevel.HIGH
    if asset_class == AssetClass.FOREIGN_EXCHANGE:
        return RiskLevel.LOW
    if asset_class == AssetClass.GOLD:
        return RiskLevel.MEDIUM
    if asset_class == AssetClass.BANK_DEPOSIT:
        return _deposit_risk(opportunity_score, term_months)
    return RiskLevel.MEDIUM


def _deposit_risk(opportunity_score: float | None, term_months: int | None) -> RiskLevel:
    if opportunity_score is None:
        level = RiskLevel.MEDIUM
    elif opportunity_score >= 68:
        level = RiskLevel.LOW
    elif opportunity_score >= 52:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.HIGH

    if term_months is None:
        return level
    if term_months > 48:
        return _bump_risk(level)
    if term_months > 36 and level == RiskLevel.LOW:
        return RiskLevel.MEDIUM
    return level


def _bump_risk(level: RiskLevel) -> RiskLevel:
    if level == RiskLevel.LOW:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH
