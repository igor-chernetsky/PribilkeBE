"""Polish bank deposit collector — aggregates parsers for individual banks."""

import logging
from datetime import timedelta

from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.collectors.pl.deposits import PL_DEPOSIT_PARSERS
from pribilka.collectors.pl.deposits.parse_result import ParserResult
from pribilka.models.enums import AssetClass, CountryCode
from pribilka.services.collector_alerts import report_deposit_parse_results

logger = logging.getLogger(__name__)


class PolandDepositCollector(BaseCollector):
    """Runs all registered PL bank deposit parsers."""

    def __init__(self):
        super().__init__(
            CollectorConfig(
                asset_class=AssetClass.BANK_DEPOSIT,
                country=CountryCode.PL,
                source_name="poland_deposits",
                refresh_interval=timedelta(hours=4),
            )
        )
        self._last_results: list[ParserResult] = []

    def collect(self) -> list[dict]:
        records: list[dict] = []
        seen_ids: set[str] = set()
        parse_results: list[ParserResult] = []

        for parser_cls in PL_DEPOSIT_PARSERS:
            parser = parser_cls()
            result = parser.run()
            parse_results.append(result)

            for offer in result.offers:
                record = offer.to_record(self.country, parser.source_name)
                if record["external_id"] in seen_ids:
                    continue
                seen_ids.add(record["external_id"])
                records.append(record)

        self._last_results = parse_results
        report_deposit_parse_results(parse_results, total_records=len(records))

        logger.info("PolandDepositCollector: %d unique deposit offers", len(records))
        return records
