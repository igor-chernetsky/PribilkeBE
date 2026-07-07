import logging
from abc import ABC, abstractmethod

import httpx

from pribilka.collectors.pl.deposits.models import DepositOffer
from pribilka.collectors.pl.deposits.parse_result import ParseStatus, ParserResult

logger = logging.getLogger(__name__)


class BankDepositParser(ABC):
    institution_name: str
    bank_slug: str
    source_name: str
    alert_on_empty: bool = True

    @staticmethod
    def _is_temporary_error(exc: Exception) -> bool:
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in {408, 425, 429, 500, 502, 503, 504}
        return False

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
                    alert_on_empty=self.alert_on_empty,
                )

            logger.info("%s: collected %d deposit offers", self.institution_name, len(offers))
            return ParserResult(
                offers=offers,
                parser_name=parser_name,
                institution_name=self.institution_name,
                status=ParseStatus.OK,
                alert_on_empty=self.alert_on_empty,
            )
        except Exception as exc:
            logger.exception("%s: deposit parsing failed", self.institution_name)
            return ParserResult(
                offers=[],
                parser_name=parser_name,
                institution_name=self.institution_name,
                status=ParseStatus.ERROR,
                error_message=str(exc),
                alert_on_empty=self.alert_on_empty,
                transient_error=self._is_temporary_error(exc),
            )

    def safe_parse(self) -> list[DepositOffer]:
        """Backward-compatible helper."""
        return self.run().offers
