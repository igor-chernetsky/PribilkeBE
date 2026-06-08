from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from pribilka.config import get_settings
from pribilka.models.bank_deposit import BankDeposit
from pribilka.models.bond import Bond
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode
from pribilka.models.financial_instrument import FinancialInstrument
from pribilka.models.fx_rate import FxRate
from pribilka.models.gold_price import GoldPrice
from pribilka.schemas.common import (
    BondResponse,
    DepositResponse,
    FxResponse,
    GoldResponse,
    MarketSummaryResponse,
)


def _default_country() -> CountryCode:
    return CountryCode(get_settings().default_country)


def list_deposits(
    db: Session,
    country: CountryCode | None = None,
    currency: CurrencyCode | None = None,
    min_rate: float | None = None,
    max_term_months: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DepositResponse], int]:
    country = country or _default_country()

    query = (
        select(BankDeposit)
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.is_active.is_(True),
            FinancialInstrument.country == country,
            FinancialInstrument.asset_class == AssetClass.BANK_DEPOSIT,
        )
        .options(joinedload(BankDeposit.instrument))
    )

    if currency:
        query = query.where(FinancialInstrument.currency == currency)
    if min_rate is not None:
        query = query.where(BankDeposit.annual_interest_rate >= min_rate)
    if max_term_months is not None:
        query = query.where(BankDeposit.term_months <= max_term_months)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    deposits = db.scalars(
        query.order_by(desc(BankDeposit.annual_interest_rate))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        DepositResponse(
            id=d.id,
            instrument_id=d.instrument_id,
            institution_name=d.institution_name,
            product_name=d.product_name,
            annual_interest_rate=float(d.annual_interest_rate),
            term_months=d.term_months,
            interest_capitalization=d.interest_capitalization,
            minimum_deposit_amount=float(d.minimum_deposit_amount)
            if d.minimum_deposit_amount
            else None,
            maximum_deposit_amount=float(d.maximum_deposit_amount)
            if d.maximum_deposit_amount
            else None,
            early_withdrawal_conditions=d.early_withdrawal_conditions,
            promotional_rate_requirements=d.promotional_rate_requirements,
            country=d.instrument.country,
            currency=d.instrument.currency,
            opportunity_score=float(d.instrument.opportunity_score)
            if d.instrument.opportunity_score
            else None,
            last_collected_at=d.instrument.last_collected_at,
        )
        for d in deposits
    ]
    return items, total


def get_deposit(
    db: Session, deposit_id: UUID, country: CountryCode | None = None
) -> DepositResponse | None:
    deposit = db.scalar(
        select(BankDeposit)
        .join(FinancialInstrument)
        .where(BankDeposit.id == deposit_id)
        .options(joinedload(BankDeposit.instrument))
    )
    if not deposit:
        return None

    if country is not None and deposit.instrument.country != country:
        return None

    return DepositResponse(
        id=deposit.id,
        instrument_id=deposit.instrument_id,
        institution_name=deposit.institution_name,
        product_name=deposit.product_name,
        annual_interest_rate=float(deposit.annual_interest_rate),
        term_months=deposit.term_months,
        interest_capitalization=deposit.interest_capitalization,
        minimum_deposit_amount=float(deposit.minimum_deposit_amount)
        if deposit.minimum_deposit_amount
        else None,
        maximum_deposit_amount=float(deposit.maximum_deposit_amount)
        if deposit.maximum_deposit_amount
        else None,
        early_withdrawal_conditions=deposit.early_withdrawal_conditions,
        promotional_rate_requirements=deposit.promotional_rate_requirements,
        country=deposit.instrument.country,
        currency=deposit.instrument.currency,
        opportunity_score=float(deposit.instrument.opportunity_score)
        if deposit.instrument.opportunity_score
        else None,
        last_collected_at=deposit.instrument.last_collected_at,
    )


def list_bonds(
    db: Session,
    country: CountryCode | None = None,
    government_only: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[BondResponse], int]:
    country = country or _default_country()

    query = (
        select(Bond)
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.is_active.is_(True),
            FinancialInstrument.country == country,
        )
        .options(joinedload(Bond.instrument))
    )

    if government_only is True:
        query = query.where(Bond.is_government.is_(True))
    elif government_only is False:
        query = query.where(Bond.is_government.is_(False))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    bonds = db.scalars(
        query.order_by(desc(Bond.yield_to_maturity))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        BondResponse(
            id=b.id,
            instrument_id=b.instrument_id,
            is_government=b.is_government,
            issuer=b.issuer,
            bond_series=b.bond_series,
            isin=b.isin,
            maturity_date=datetime.combine(b.maturity_date, datetime.min.time()),
            coupon_rate=float(b.coupon_rate),
            yield_to_maturity=float(b.yield_to_maturity) if b.yield_to_maturity else None,
            market_price=float(b.market_price) if b.market_price else None,
            country=b.instrument.country,
            currency=b.instrument.currency,
            opportunity_score=float(b.instrument.opportunity_score)
            if b.instrument.opportunity_score
            else None,
            last_collected_at=b.instrument.last_collected_at,
        )
        for b in bonds
    ]
    return items, total


def get_latest_gold(db: Session, country: CountryCode | None = None) -> GoldResponse | None:
    country = country or _default_country()
    gold = db.scalar(
        select(GoldPrice)
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.country == country,
            FinancialInstrument.asset_class == AssetClass.GOLD,
            FinancialInstrument.is_active.is_(True),
        )
        .options(joinedload(GoldPrice.instrument))
        .order_by(desc(GoldPrice.updated_at))
        .limit(1)
    )
    if not gold:
        return None

    return GoldResponse(
        id=gold.id,
        instrument_id=gold.instrument_id,
        spot_price=float(gold.spot_price),
        buy_price=float(gold.buy_price) if gold.buy_price else None,
        sell_price=float(gold.sell_price) if gold.sell_price else None,
        daily_change_percent=float(gold.daily_change_percent)
        if gold.daily_change_percent
        else None,
        weekly_change_percent=float(gold.weekly_change_percent)
        if gold.weekly_change_percent
        else None,
        monthly_change_percent=float(gold.monthly_change_percent)
        if gold.monthly_change_percent
        else None,
        annual_change_percent=float(gold.annual_change_percent)
        if gold.annual_change_percent
        else None,
        currency=gold.instrument.currency,
        last_collected_at=gold.instrument.last_collected_at,
    )


def list_fx_rates(db: Session, country: CountryCode | None = None) -> list[FxResponse]:
    country = country or _default_country()
    rates = db.scalars(
        select(FxRate)
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.country == country,
            FinancialInstrument.asset_class == AssetClass.FOREIGN_EXCHANGE,
            FinancialInstrument.is_active.is_(True),
        )
        .options(joinedload(FxRate.instrument))
    ).all()

    return [
        FxResponse(
            id=r.id,
            instrument_id=r.instrument_id,
            base_currency=r.base_currency,
            quote_currency=r.quote_currency,
            bid_price=float(r.bid_price),
            ask_price=float(r.ask_price),
            mid_market_rate=float(r.mid_market_rate),
            daily_change_percent=float(r.daily_change_percent) if r.daily_change_percent else None,
            weekly_change_percent=float(r.weekly_change_percent)
            if r.weekly_change_percent
            else None,
            monthly_change_percent=float(r.monthly_change_percent)
            if r.monthly_change_percent
            else None,
            source_name=r.instrument.source_name,
            last_collected_at=r.instrument.last_collected_at,
        )
        for r in rates
    ]


def get_market_summary(db: Session, country: CountryCode | None = None) -> MarketSummaryResponse:
    country = country or _default_country()

    deposits_count = db.scalar(
        select(func.count())
        .select_from(BankDeposit)
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.country == country,
            FinancialInstrument.is_active.is_(True),
        )
    ) or 0

    bonds_count = db.scalar(
        select(func.count())
        .select_from(Bond)
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.country == country,
            FinancialInstrument.is_active.is_(True),
        )
    ) or 0

    best_deposit_rate = db.scalar(
        select(func.max(BankDeposit.annual_interest_rate))
        .join(FinancialInstrument)
        .where(FinancialInstrument.country == country, FinancialInstrument.is_active.is_(True))
    )

    best_bond_yield = db.scalar(
        select(func.max(Bond.yield_to_maturity))
        .join(FinancialInstrument)
        .where(FinancialInstrument.country == country, FinancialInstrument.is_active.is_(True))
    )

    gold = get_latest_gold(db, country)
    fx_rates = list_fx_rates(db, country)

    usd_pln = next(
        (r.mid_market_rate for r in fx_rates if r.base_currency == CurrencyCode.USD), None
    )
    eur_pln = next(
        (r.mid_market_rate for r in fx_rates if r.base_currency == CurrencyCode.EUR), None
    )

    latest_update = db.scalar(
        select(func.max(FinancialInstrument.last_collected_at)).where(
            FinancialInstrument.country == country
        )
    )

    return MarketSummaryResponse(
        country=country,
        deposits_count=deposits_count,
        bonds_count=bonds_count,
        best_deposit_rate=float(best_deposit_rate) if best_deposit_rate else None,
        best_bond_yield=float(best_bond_yield) if best_bond_yield else None,
        gold_spot_price=gold.spot_price if gold else None,
        usd_pln_rate=usd_pln,
        eur_pln_rate=eur_pln,
        updated_at=latest_update,
    )
