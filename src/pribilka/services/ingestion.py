from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.models.bank_deposit import BankDeposit
from pribilka.models.bond import Bond
from pribilka.models.enums import AssetClass
from pribilka.models.financial_instrument import FinancialInstrument
from pribilka.models.fx_rate import FxRate
from pribilka.models.gold_price import GoldPrice
from pribilka.models.rate_history import RateHistory
from pribilka.services.event_engine import detect_rate_change
from pribilka.services.opportunity_scoring import calculate_deposit_score


def _get_or_create_instrument(
    db: Session, record: dict, asset_class: AssetClass
) -> FinancialInstrument:
    instrument = db.scalar(
        select(FinancialInstrument).where(
            FinancialInstrument.external_id == record["external_id"],
            FinancialInstrument.asset_class == asset_class,
        )
    )

    if instrument is None:
        instrument = FinancialInstrument(
            asset_class=asset_class,
            country=record["country"],
            currency=record["currency"],
            external_id=record["external_id"],
            source_url=record.get("source_url", ""),
            source_name=record.get("source_name", ""),
        )
        db.add(instrument)
        db.flush()

    instrument.last_collected_at = datetime.now(UTC)
    instrument.source_url = record.get("source_url", instrument.source_url)
    instrument.source_name = record.get("source_name", instrument.source_name)
    instrument.is_active = True
    return instrument


def _record_history(db: Session, instrument_id, value: Decimal, value_type: str):
    db.add(
        RateHistory(
            instrument_id=instrument_id,
            value=float(value),
            value_type=value_type,
            recorded_at=datetime.now(UTC),
        )
    )


def ingest_deposits(db: Session, records: list[dict]) -> int:
    if not records:
        return 0

    max_rate = max(Decimal(str(r["annual_interest_rate"])) for r in records)
    count = 0

    for record in records:
        instrument = _get_or_create_instrument(db, record, AssetClass.BANK_DEPOSIT)
        new_rate = Decimal(str(record["annual_interest_rate"]))

        deposit = db.scalar(
            select(BankDeposit).where(BankDeposit.instrument_id == instrument.id)
        )

        previous_rate = Decimal(str(deposit.annual_interest_rate)) if deposit else None

        if deposit is None:
            deposit = BankDeposit(
                instrument_id=instrument.id,
                institution_name=record["institution_name"],
                product_name=record["product_name"],
                annual_interest_rate=new_rate,
                term_months=record["term_months"],
                interest_capitalization=record.get("interest_capitalization"),
                minimum_deposit_amount=record.get("minimum_deposit_amount"),
                maximum_deposit_amount=record.get("maximum_deposit_amount"),
                early_withdrawal_conditions=record.get("early_withdrawal_conditions"),
                promotional_rate_requirements=record.get("promotional_rate_requirements"),
            )
            db.add(deposit)
        else:
            deposit.annual_interest_rate = new_rate
            deposit.term_months = record["term_months"]
            deposit.institution_name = record["institution_name"]
            deposit.product_name = record["product_name"]

        detect_rate_change(db, instrument.id, previous_rate, new_rate, "rate")
        _record_history(db, instrument.id, new_rate, "rate")

        instrument.opportunity_score = calculate_deposit_score(
            new_rate, record["term_months"], max_rate
        )
        count += 1

    db.commit()
    return count


def ingest_bonds(db: Session, records: list[dict]) -> int:
    count = 0
    for record in records:
        asset_class = (
            AssetClass.GOVERNMENT_BOND if record.get("is_government") else AssetClass.CORPORATE_BOND
        )
        instrument = _get_or_create_instrument(db, record, asset_class)

        bond = db.scalar(select(Bond).where(Bond.instrument_id == instrument.id))
        ytm = Decimal(str(record["yield_to_maturity"])) if record.get("yield_to_maturity") else None
        previous_ytm = Decimal(str(bond.yield_to_maturity)) if bond and bond.yield_to_maturity else None

        if bond is None:
            bond = Bond(
                instrument_id=instrument.id,
                is_government=record.get("is_government", False),
                issuer=record["issuer"],
                bond_series=record.get("bond_series"),
                isin=record.get("isin"),
                maturity_date=record["maturity_date"],
                coupon_rate=record["coupon_rate"],
                yield_to_maturity=ytm,
                market_price=record.get("market_price"),
            )
            db.add(bond)
        else:
            bond.yield_to_maturity = ytm
            bond.market_price = record.get("market_price")
            bond.coupon_rate = record["coupon_rate"]

        if ytm is not None:
            detect_rate_change(db, instrument.id, previous_ytm, ytm, "yield")
            _record_history(db, instrument.id, ytm, "yield")

        count += 1

    db.commit()
    return count


def ingest_fx(db: Session, records: list[dict]) -> int:
    count = 0
    for record in records:
        instrument = _get_or_create_instrument(db, record, AssetClass.FOREIGN_EXCHANGE)
        mid = Decimal(str(record["mid_market_rate"]))

        fx = db.scalar(select(FxRate).where(FxRate.instrument_id == instrument.id))
        previous = Decimal(str(fx.mid_market_rate)) if fx else None

        if fx is None:
            fx = FxRate(
                instrument_id=instrument.id,
                base_currency=record["base_currency"],
                quote_currency=record["quote_currency"],
                bid_price=record["bid_price"],
                ask_price=record["ask_price"],
                mid_market_rate=mid,
                daily_change_percent=record.get("daily_change_percent"),
            )
            db.add(fx)
        else:
            fx.bid_price = record["bid_price"]
            fx.ask_price = record["ask_price"]
            fx.mid_market_rate = mid
            if record.get("daily_change_percent") is not None:
                fx.daily_change_percent = record["daily_change_percent"]

        detect_rate_change(db, instrument.id, previous, mid, "mid_rate")
        _record_history(db, instrument.id, mid, "mid_rate")
        count += 1

    db.commit()
    return count


def ingest_gold(db: Session, records: list[dict]) -> int:
    count = 0
    for record in records:
        instrument = _get_or_create_instrument(db, record, AssetClass.GOLD)
        spot = Decimal(str(record["spot_price"]))

        gold = db.scalar(select(GoldPrice).where(GoldPrice.instrument_id == instrument.id))
        previous = Decimal(str(gold.spot_price)) if gold else None

        if gold is None:
            gold = GoldPrice(
                instrument_id=instrument.id,
                spot_price=spot,
                buy_price=record.get("buy_price"),
                sell_price=record.get("sell_price"),
                daily_change_percent=record.get("daily_change_percent"),
            )
            db.add(gold)
        else:
            gold.spot_price = spot
            gold.buy_price = record.get("buy_price")
            gold.sell_price = record.get("sell_price")
            if record.get("daily_change_percent") is not None:
                gold.daily_change_percent = record["daily_change_percent"]

        detect_rate_change(db, instrument.id, previous, spot, "spot_price")
        _record_history(db, instrument.id, spot, "spot_price")
        count += 1

    db.commit()
    return count
