from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pribilka.config import get_settings
from pribilka.models.bank_deposit import BankDeposit
from pribilka.models.bond import Bond
from pribilka.models.enums import AssetClass
from pribilka.schemas.common import BondResponse, DepositResponse
from pribilka.schemas.insights import InsightResponse
from pribilka.services import market_data


def _avg_deposit_rate(db: Session) -> float | None:
    value = db.scalar(select(func.avg(BankDeposit.annual_interest_rate)))
    return float(value) if value is not None else None


def _avg_bond_yield(db: Session) -> float | None:
    value = db.scalar(
        select(func.avg(func.coalesce(Bond.yield_to_maturity, Bond.coupon_rate)))
    )
    return float(value) if value is not None else None


def _build_deposit_insight(deposit: DepositResponse, market_avg: float | None) -> InsightResponse:
    highlights: list[str] = []
    rate = deposit.annual_interest_rate

    if market_avg is not None:
        diff = rate - market_avg
        direction = "above" if diff >= 0 else "below"
        highlights.append(
            f"Yield {rate:.2f}% is {abs(diff):.2f}% {direction} the market average ({market_avg:.2f}%)."
        )
    else:
        highlights.append(f"Annual yield is {rate:.2f}%.")

    highlights.append(f"Term: {deposit.term_months} months at {deposit.institution_name}.")

    if deposit.opportunity_score is not None:
        highlights.append(f"Opportunity score: {deposit.opportunity_score:.0f}/100.")

    if deposit.minimum_deposit_amount:
        highlights.append(f"Minimum deposit: {deposit.minimum_deposit_amount:,.0f} {deposit.currency}.")

    if deposit.promotional_rate_requirements:
        highlights.append(f"Note: {deposit.promotional_rate_requirements}")

    summary = (
        f"{deposit.product_name} from {deposit.institution_name} offers {rate:.2f}% APY. "
        + (highlights[0] if highlights else "")
    )

    return InsightResponse(
        product_id=deposit.id,
        asset_class=AssetClass.BANK_DEPOSIT,
        summary=summary,
        highlights=highlights,
        generated_at=datetime.now(UTC),
        source="rules",
    )


def _build_bond_insight(bond: BondResponse, market_avg: float | None) -> InsightResponse:
    highlights: list[str] = []
    ytm = bond.yield_to_maturity if bond.yield_to_maturity is not None else bond.coupon_rate
    bond_type = "government" if bond.is_government else "corporate"

    if market_avg is not None:
        diff = ytm - market_avg
        direction = "above" if diff >= 0 else "below"
        highlights.append(
            f"Yield {ytm:.2f}% is {abs(diff):.2f}% {direction} the average bond yield ({market_avg:.2f}%)."
        )
    else:
        highlights.append(f"Effective yield is {ytm:.2f}%.")

    highlights.append(f"{bond_type.capitalize()} bond from {bond.issuer}.")
    if bond.bond_series:
        highlights.append(f"Series: {bond.bond_series}.")
    if bond.opportunity_score is not None:
        highlights.append(f"Opportunity score: {bond.opportunity_score:.0f}/100.")

    summary = (
        f"{bond.issuer} {bond.bond_series or 'bond'} yields {ytm:.2f}%. "
        + (highlights[0] if highlights else "")
    )

    asset_class = AssetClass.GOVERNMENT_BOND if bond.is_government else AssetClass.CORPORATE_BOND
    return InsightResponse(
        product_id=bond.id,
        asset_class=asset_class,
        summary=summary,
        highlights=highlights,
        generated_at=datetime.now(UTC),
        source="rules",
    )


def _maybe_enhance_with_openai(insight: InsightResponse) -> InsightResponse:
    settings = get_settings()
    if not settings.openai_api_key:
        return insight

    try:
        import httpx

        prompt = (
            "Rewrite this investment product insight in 2 concise sentences. "
            "Do not give buy/sell advice. Data:\n"
            f"{insight.summary}\n" + "\n".join(insight.highlights)
        )
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
            },
            timeout=20,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        return insight.model_copy(update={"summary": content, "source": "openai"})
    except Exception:
        return insight


def get_deposit_insight(db: Session, deposit_id: UUID, country) -> InsightResponse | None:
    deposit = market_data.get_deposit(db, deposit_id, country=country)
    if not deposit:
        return None
    insight = _build_deposit_insight(deposit, _avg_deposit_rate(db))
    return _maybe_enhance_with_openai(insight)


def get_bond_insight(db: Session, bond_id: UUID, country) -> InsightResponse | None:
    bonds, _ = market_data.list_bonds(db, country=country, page=1, page_size=500)
    bond = next((b for b in bonds if b.id == bond_id), None)
    if not bond:
        return None
    insight = _build_bond_insight(bond, _avg_bond_yield(db))
    return _maybe_enhance_with_openai(insight)
