from dataclasses import dataclass
from enum import Enum


class RentalCollectorIssueKind(str, Enum):
    FETCH_ERROR = "fetch_error"
    BOT_WALL = "bot_wall"
    EMPTY_PARSE = "empty_parse"


@dataclass(frozen=True)
class RentalCollectorIssue:
    city_slug: str
    listing_type: str
    room_count: int
    page: int
    url: str
    kind: RentalCollectorIssueKind
    error_message: str | None = None
