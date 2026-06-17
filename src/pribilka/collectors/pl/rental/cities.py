from dataclasses import dataclass


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

OTODOM_ROOM_PARAM = {
    1: "ONE",
    2: "TWO",
    3: "THREE",
}
