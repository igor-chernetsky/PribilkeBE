from datetime import datetime
from zoneinfo import ZoneInfo

from pribilka.collectors.pl.rental.cities import (
    POLAND_RENTAL_CITIES,
    RENTAL_CITY_PARTITIONS,
    current_rental_partition,
    rental_cities_for_partition,
)

WARSAW = ZoneInfo("Europe/Warsaw")


def test_rental_partitions_cover_all_cities_without_overlap():
    seen: list[str] = []
    for partition in range(RENTAL_CITY_PARTITIONS):
        batch = rental_cities_for_partition(partition)
        assert batch
        slugs = [city.slug for city in batch]
        assert not set(slugs) & set(seen)
        seen.extend(slugs)

    assert seen == [city.slug for city in POLAND_RENTAL_CITIES]


def test_rental_partition_sizes_are_balanced():
    sizes = [len(rental_cities_for_partition(partition)) for partition in range(RENTAL_CITY_PARTITIONS)]
    assert sizes == [3, 3, 2, 2]
    assert rental_cities_for_partition(0)[0].slug == "warszawa"
    assert rental_cities_for_partition(3)[-1].slug == "bialystok"


def test_current_rental_partition_rotates_every_three_hours():
    assert current_rental_partition(datetime(2026, 6, 7, 1, 30, tzinfo=WARSAW)) == 0
    assert current_rental_partition(datetime(2026, 6, 7, 3, 30, tzinfo=WARSAW)) == 1
    assert current_rental_partition(datetime(2026, 6, 7, 8, 0, tzinfo=WARSAW)) == 2
    assert current_rental_partition(datetime(2026, 6, 7, 11, 59, tzinfo=WARSAW)) == 3
    assert current_rental_partition(datetime(2026, 6, 7, 12, 0, tzinfo=WARSAW)) == 0
