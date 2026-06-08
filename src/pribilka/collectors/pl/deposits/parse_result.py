from dataclasses import dataclass
from enum import Enum

from pribilka.collectors.pl.deposits.models import DepositOffer


class ParseStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    ERROR = "error"


@dataclass
class ParserResult:
    offers: list[DepositOffer]
    parser_name: str
    institution_name: str
    status: ParseStatus
    error_message: str | None = None

    @property
    def offer_count(self) -> int:
        return len(self.offers)
