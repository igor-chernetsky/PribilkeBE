from dataclasses import dataclass


@dataclass(frozen=True)
class RentalCity:
    slug: str
    name_pl: str
    name_en: str
    otodom_slug: str


POLAND_RENTAL_CITIES: tuple[RentalCity, ...] = (
    RentalCity("warszawa", "Warszawa", "Warsaw", "warszawa"),
    RentalCity("krakow", "Kraków", "Krakow", "krakow"),
    RentalCity("wroclaw", "Wrocław", "Wroclaw", "wroclaw"),
    RentalCity("poznan", "Poznań", "Poznan", "poznan"),
    RentalCity("gdansk", "Gdańsk", "Gdansk", "gdansk"),
    RentalCity("lodz", "Łódź", "Lodz", "lodz"),
    RentalCity("katowice", "Katowice", "Katowice", "katowice"),
    RentalCity("lublin", "Lublin", "Lublin", "lublin"),
    RentalCity("szczecin", "Szczecin", "Szczecin", "szczecin"),
    RentalCity("bialystok", "Białystok", "Bialystok", "bialystok"),
)

TRACKED_ROOM_COUNTS: tuple[int, ...] = (1, 2, 3)

OTODOM_ROOM_PARAM = {
    1: "ONE",
    2: "TWO",
    3: "THREE",
}
