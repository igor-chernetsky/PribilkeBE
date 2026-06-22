from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pribilka.db.base import Base
from pribilka.models.rental_yield_snapshot import RentalYieldSnapshot
from pribilka.services.rental_market import get_avg_rental_yield_glance, get_rental_yield_glance

_RENTAL_TABLES = (RentalYieldSnapshot.__table__,)


def _make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=list(_RENTAL_TABLES))
    return sessionmaker(bind=engine)()


def _seed_rows(db, period: datetime, older: datetime) -> None:
    for city_slug, gross_yield in (("warszawa", 5.0), ("krakow", 7.0), ("wroclaw", 6.0)):
        db.add(
            RentalYieldSnapshot(
                city_slug=city_slug,
                room_count=2,
                period_start=period,
                sale_sample_size=10,
                rent_sample_size=10,
                gross_yield_median=gross_yield,
            )
        )
        db.add(
            RentalYieldSnapshot(
                city_slug=city_slug,
                room_count=3,
                period_start=period,
                sale_sample_size=10,
                rent_sample_size=10,
                gross_yield_median=99.0,
            )
        )
        db.add(
            RentalYieldSnapshot(
                city_slug=city_slug,
                room_count=2,
                period_start=older,
                sale_sample_size=10,
                rent_sample_size=10,
                gross_yield_median=1.0,
            )
        )


def test_get_rental_yield_glance_picks_best_city_in_latest_period():
    db = _make_session()
    period = datetime(2026, 6, 19, 12, tzinfo=UTC)
    older = datetime(2026, 6, 18, 12, tzinfo=UTC)
    _seed_rows(db, period, older)
    db.commit()

    glance = get_rental_yield_glance(db)

    assert glance.room_count == 2
    assert glance.best_yield == 7.0
    assert glance.city_slug == "krakow"
    assert glance.city_name_pl == "Kraków"
    assert glance.city_name_en == "Krakow"
    assert glance.updated_at == period.replace(tzinfo=None)


def test_get_avg_rental_yield_glance_averages_latest_period():
    db = _make_session()
    period = datetime(2026, 6, 19, 12, tzinfo=UTC)
    older = datetime(2026, 6, 18, 12, tzinfo=UTC)
    _seed_rows(db, period, older)
    db.commit()

    avg_yield, room_count = get_avg_rental_yield_glance(db)

    assert room_count == 2
    assert avg_yield == 6.0


def test_get_rental_yield_glance_returns_empty_without_data():
    db = _make_session()

    glance = get_rental_yield_glance(db)

    assert glance.best_yield is None
    assert glance.city_slug is None
