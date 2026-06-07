from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ScoringWeights:
    yield_weight: float = 0.40
    liquidity_weight: float = 0.25
    reliability_weight: float = 0.20
    term_weight: float = 0.15


DEFAULT_WEIGHTS = ScoringWeights()


def calculate_deposit_score(
    annual_rate: Decimal,
    term_months: int,
    max_rate_in_market: Decimal,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> float:
    """Score deposits 0–100 based on yield and term (shorter = better)."""
    if max_rate_in_market <= 0:
        yield_score = 0.0
    else:
        yield_score = min(float(annual_rate / max_rate_in_market) * 100, 100)

    liquidity_score = 80.0  # deposits are generally liquid at maturity
    reliability_score = 70.0  # baseline; refined per institution later
    term_score = max(0.0, 100.0 - (term_months / 36) * 100)

    return round(
        yield_score * weights.yield_weight
        + liquidity_score * weights.liquidity_weight
        + reliability_score * weights.reliability_weight
        + term_score * weights.term_weight,
        2,
    )


def calculate_bond_score(
    ytm: Decimal | None,
    coupon_rate: Decimal,
    liquidity_score: float | None,
    max_ytm_in_market: Decimal,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> float:
    effective_yield = ytm if ytm is not None else coupon_rate

    if max_ytm_in_market <= 0:
        yield_score = 0.0
    else:
        yield_score = min(float(effective_yield / max_ytm_in_market) * 100, 100)

    liquidity = liquidity_score if liquidity_score is not None else 50.0
    reliability_score = 60.0
    term_score = 50.0

    return round(
        yield_score * weights.yield_weight
        + liquidity * weights.liquidity_weight
        + reliability_score * weights.reliability_weight
        + term_score * weights.term_weight,
        2,
    )
