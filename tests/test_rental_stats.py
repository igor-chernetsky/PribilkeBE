import json
from pathlib import Path

from pribilka.models.enums import RentalListingType
from pribilka.services.rental_stats import distribution_stats, truncate_to_12h_period, yield_stats

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "otodom_search_sample.json"


def test_distribution_stats_percentiles():
    stats = distribution_stats([100, 200, 300, 400, 500])
    assert stats.sample_size == 5
    assert stats.p25 == 200
    assert stats.median == 300
    assert stats.p75 == 400


def test_yield_stats_range():
    stats = yield_stats(
        sale_prices=[400_000, 500_000, 600_000],
        rent_prices=[2_000, 2_500, 3_000],
    )
    assert stats.sale_sample_size == 3
    assert stats.rent_sample_size == 3
    assert stats.gross_yield_median is not None
    assert stats.gross_yield_p25 is not None
    assert stats.gross_yield_p75 is not None
    assert stats.gross_yield_p25 <= stats.gross_yield_median <= stats.gross_yield_p75


def test_truncate_to_12h_period():
    from datetime import UTC, datetime

    morning = datetime(2026, 6, 7, 9, 15, tzinfo=UTC)
    evening = datetime(2026, 6, 7, 21, 15, tzinfo=UTC)
    assert truncate_to_12h_period(morning).hour == 0
    assert truncate_to_12h_period(evening).hour == 12


def test_build_otodom_search_url_includes_voivodeship():
    from pribilka.collectors.pl.rental.otodom import build_otodom_search_url

    url = build_otodom_search_url(
        location_path="mazowieckie/warszawa",
        listing_type=RentalListingType.SALE,
        room_count=2,
        page=1,
    )
    assert "/mieszkanie/mazowieckie/warszawa?" in url
    assert "roomsNumber=%5BTWO%5D" in url


def test_parse_otodom_fixture():
    from pribilka.collectors.pl.rental.otodom import parse_otodom_search_html

    payload = json.loads(FIXTURE_PATH.read_text())
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'
    listings = parse_otodom_search_html(
        html,
        city_slug="warszawa",
        listing_type=RentalListingType.SALE,
        room_count=2,
    )
    assert len(listings) >= 2
    assert all(item["price_pln"] > 0 for item in listings)
