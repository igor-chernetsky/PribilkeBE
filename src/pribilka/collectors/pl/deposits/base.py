import logging
from abc import ABC, abstractmethod

from pribilka.collectors.pl.deposits.models import DepositOffer
from pribilka.collectors.pl.deposits.parse_result import ParseStatus, ParserResult

logger = logging.getLogger(__name__)


class BankDepositParser(ABC):
    institution_name: str
    bank_slug: str
    source_name: str

    @abstractmethod
    def parse(self) -> list[DepositOffer]:
        """Fetch and parse deposit offers from the bank's public pages."""

    def run(self) -> ParserResult:
        parser_name = self.__class__.__name__
        try:
            offers = self.parse()
            if not offers:
                logger.warning("%s: parser returned 0 offers", self.institution_name)
                return ParserResult(
                    offers=[],
                    parser_name=parser_name,
                    institution_name=self.institution_name,
                    status=ParseStatus.EMPTY,
                    error_message="Parser returned no offers — possible HTML layout change",
                )

            logger.info("%s: collected %d deposit offers", self.institution_name, len(offers))
            return ParserResult(
                offers=offers,
                parser_name=parser_name,
                institution_name=self.institution_name,
                status=ParseStatus.OK,
            )
        except Exception as exc:
            logger.exception("%s: deposit parsing failed", self.institution_name)
            return ParserResult(
                offers=[],
                parser_name=parser_name,
                institution_name=self.institution_name,
                status=ParseStatus.ERROR,
                error_message=str(exc),
            )

    def safe_parse(self) -> list[DepositOffer]:
        """Backward-compatible helper."""
        return self.run().offers
