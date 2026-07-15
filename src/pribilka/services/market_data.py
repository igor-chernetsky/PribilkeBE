from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from pribilka.config import get_settings
from pribilka.models.bank_deposit import BankDeposit
from pribilka.models.bond import Bond
from pribilka.models.enums import AssetClass, CountryCode, CurrencyCode, RiskLevel
from pribilka.models.financial_instrument import FinancialInstrument
from pribilka.models.fx_rate import FxRate
from pribilka.models.gold_price import GoldPrice
from pribilka.models.weekly_digest import WeeklyDigest
from pribilka.schemas.common import (
    BondResponse,
    DepositResponse,
    DigestTeaserResponse,
    FxResponse,
    GoldResponse,
    MarketSummaryResponse,
)
from pribilka.services.institution_slugs import resolve_bank_slug
from pribilka.services.rental_market import RentalYieldGlance, get_rental_yield_glance
from pribilka.services.risk_levels import resolve_risk_level


def _score_value(instrument: FinancialInstrument) -> float | None:
    if instrument.opportunity_score is None:
        return None
    return float(instrument.opportunity_score)


def _deposit_risk_level(deposit: BankDeposit) -> RiskLevel:
    return resolve_risk_level(
        deposit.instrument.asset_class,
        _score_value(deposit.instrument),
        term_months=deposit.term_months,
    )


def _bond_risk_level(bond: Bond) -> RiskLevel:
    return resolve_risk_level(
        bond.instrument.asset_class,
        _score_value(bond.instrument),
        is_government=bond.is_government,
    )


def _deposit_response(deposit: BankDeposit) -> DepositResponse:
    return DepositResponse(
        id=deposit.id,
        instrument_id=deposit.instrument_id,
        institution_name=deposit.institution_name,
        bank_slug=resolve_bank_slug(deposit.institution_name, deposit.bank_slug),
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
        risk_level=_deposit_risk_level(deposit),
        last_collected_at=deposit.instrument.last_collected_at,
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

    items = [_deposit_response(d) for d in deposits]
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

    return _deposit_response(deposit)


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
            risk_level=_bond_risk_level(b),
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
        risk_level=resolve_risk_level(AssetClass.GOLD),
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
            risk_level=resolve_risk_level(AssetClass.FOREIGN_EXCHANGE),
            last_collected_at=r.instrument.last_collected_at,
        )
        for r in rates
    ]


def _format_rental_highlight(city_name: str, yield_pct: float, *, locale: str) -> str:
    if locale.lower().startswith("pl"):
        return f"Najlepsza rentowność: {city_name} · {yield_pct:.1f}%"
    return f"Top rental yield: {city_name} · {yield_pct:.1f}%"


def _digest_locale_content(digest: WeeklyDigest, locale: str) -> tuple[str, str]:
    data = digest.content_pl if locale.lower().startswith("pl") else digest.content_en
    return data.get("title", ""), data.get("summary", "")


def _build_digest_teaser(db: Session, country: CountryCode, rental: RentalYieldGlance) -> DigestTeaserResponse | None:
    highlight_pl = None
    highlight_en = None
    if rental.best_yield is not None and rental.city_name_pl and rental.city_name_en:
        highlight_pl = _format_rental_highlight(rental.city_name_pl, rental.best_yield, locale="pl")
        highlight_en = _format_rental_highlight(rental.city_name_en, rental.best_yield, locale="en")

    digest = db.scalar(
        select(WeeklyDigest)
        .where(WeeklyDigest.country == country)
        .order_by(desc(WeeklyDigest.week_start))
        .limit(1)
    )
    if digest is None:
        if highlight_pl is None:
            return None
        return DigestTeaserResponse(
            available=False,
            highlight_pl=highlight_pl,
            highlight_en=highlight_en,
        )

    content_pl = _digest_locale_content(digest, "pl")
    content_en = _digest_locale_content(digest, "en")
    return DigestTeaserResponse(
        available=True,
        week_start=digest.week_start,
        title_pl=content_pl[0],
        title_en=content_en[0],
        summary_pl=content_pl[1],
        summary_en=content_en[1],
        highlight_pl=highlight_pl or content_pl[1],
        highlight_en=highlight_en or content_en[1],
    )


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

    avg_deposit_rate = db.scalar(
        select(func.avg(BankDeposit.annual_interest_rate))
        .join(FinancialInstrument)
        .where(FinancialInstrument.country == country, FinancialInstrument.is_active.is_(True))
    )

    avg_bond_yield = db.scalar(
        select(func.avg(Bond.yield_to_maturity))
        .join(FinancialInstrument)
        .where(
            FinancialInstrument.country == country,
            FinancialInstrument.is_active.is_(True),
            Bond.yield_to_maturity.is_not(None),
        )
    )

    gold = get_latest_gold(db, country)
    fx_rates = list_fx_rates(db, country)

    usd_pln = next(
        (r for r in fx_rates if r.base_currency == CurrencyCode.USD), None
    )
    eur_pln = next(
        (r for r in fx_rates if r.base_currency == CurrencyCode.EUR), None
    )

    latest_update = db.scalar(
        select(func.max(FinancialInstrument.last_collected_at)).where(
            FinancialInstrument.country == country
        )
    )

    rental_glance = get_rental_yield_glance(db)
    digest_teaser = _build_digest_teaser(db, country, rental_glance)

    return MarketSummaryResponse(
        country=country,
        deposits_count=deposits_count,
        bonds_count=bonds_count,
        best_deposit_rate=float(best_deposit_rate) if best_deposit_rate else None,
        best_bond_yield=float(best_bond_yield) if best_bond_yield else None,
        avg_deposit_yield=float(avg_deposit_rate) if avg_deposit_rate is not None else None,
        avg_bond_yield=float(avg_bond_yield) if avg_bond_yield is not None else None,
        gold_spot_price=gold.spot_price if gold else None,
        gold_daily_change_percent=gold.daily_change_percent if gold else None,
        usd_pln_rate=usd_pln.mid_market_rate if usd_pln else None,
        eur_pln_rate=eur_pln.mid_market_rate if eur_pln else None,
        usd_pln_daily_change_percent=usd_pln.daily_change_percent if usd_pln else None,
        eur_pln_daily_change_percent=eur_pln.daily_change_percent if eur_pln else None,
        best_rental_yield=rental_glance.best_yield,
        best_rental_yield_city_slug=rental_glance.city_slug,
        best_rental_yield_city_name_pl=rental_glance.city_name_pl,
        best_rental_yield_city_name_en=rental_glance.city_name_en,
        rental_yield_room_count=rental_glance.room_count,
        rental_yield_updated_at=rental_glance.updated_at,
        digest_teaser=digest_teaser,
        updated_at=latest_update,
    )
