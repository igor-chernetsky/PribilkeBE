from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RentalCity:
    slug: str
    name_pl: str
    name_en: str
    otodom_slug: str
    otodom_location_path: str


POLAND_RENTAL_CITIES: tuple[RentalCity, ...] = (
    RentalCity("warszawa", "Warszawa", "Warsaw", "warszawa", "mazowieckie/warszawa"),
    RentalCity("krakow", "Kraków", "Krakow", "krakow", "malopolskie/krakow"),
    RentalCity("wroclaw", "Wrocław", "Wroclaw", "wroclaw", "dolnoslaskie/wroclaw"),
    RentalCity("poznan", "Poznań", "Poznan", "poznan", "wielkopolskie/poznan"),
    RentalCity("gdansk", "Gdańsk", "Gdansk", "gdansk", "pomorskie/gdansk"),
    RentalCity("lodz", "Łódź", "Lodz", "lodz", "lodzkie/lodz"),
    RentalCity("katowice", "Katowice", "Katowice", "katowice", "slaskie/katowice"),
    RentalCity("lublin", "Lublin", "Lublin", "lublin", "lubelskie/lublin"),
    RentalCity("szczecin", "Szczecin", "Szczecin", "szczecin", "zachodniopomorskie/szczecin"),
    RentalCity("bialystok", "Białystok", "Bialystok", "bialystok", "podlaskie/bialystok"),
)

TRACKED_ROOM_COUNTS: tuple[int, ...] = (1, 2, 3)

RENTAL_CITY_PARTITIONS = 4

OTODOM_ROOM_PARAM = {
    1: "ONE",
    2: "TWO",
    3: "THREE",
}


def rental_cities_for_partition(partition: int, *, partitions: int = RENTAL_CITY_PARTITIONS) -> tuple[RentalCity, ...]:
    """Split the city list into near-equal shards for staggered collector runs."""
    if partition < 0 or partition >= partitions:
        raise ValueError(f"partition must be 0..{partitions - 1}, got {partition}")

    cities = POLAND_RENTAL_CITIES
    base, extra = divmod(len(cities), partitions)
    sizes = [base + (1 if index < extra else 0) for index in range(partitions)]
    start = sum(sizes[:partition])
    end = start + sizes[partition]
    return cities[start:end]


def current_rental_partition(
    moment: datetime | None = None,
    *,
    partitions: int = RENTAL_CITY_PARTITIONS,
) -> int:
    """Rotate partition every 3 hours (0–2 → 0, 3–5 → 1, …) in Warsaw time."""
    from zoneinfo import ZoneInfo

    moment = moment or datetime.now(ZoneInfo("Europe/Warsaw"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo("Europe/Warsaw"))
    else:
        moment = moment.astimezone(ZoneInfo("Europe/Warsaw"))
    return (moment.hour // 3) % partitions
