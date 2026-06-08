"""Polish government savings bonds collector."""

import logging
from datetime import timedelta

from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.collectors.pl.bonds import PL_BOND_PARSERS
from pribilka.models.enums import AssetClass, CountryCode

logger = logging.getLogger(__name__)


class PolandBondCollector(BaseCollector):
    def __init__(self):
        super().__init__(
            CollectorConfig(
                asset_class=AssetClass.GOVERNMENT_BOND,
                country=CountryCode.PL,
                source_name="poland_bonds",
                refresh_interval=timedelta(hours=1),
            )
        )

    def collect(self) -> list[dict]:
        records: list[dict] = []
        seen_ids: set[str] = set()

        for parser_cls in PL_BOND_PARSERS:
            parser = parser_cls()
            try:
                offers = parser.parse()
            except Exception:
                logger.exception("Bond parser %s failed", parser.__class__.__name__)
                continue

            for offer in offers:
                record = {**offer, "country": self.country, "source_name": parser.source_name}
                if record["external_id"] in seen_ids:
                    continue
                seen_ids.add(record["external_id"])
                records.append(record)

        logger.info("PolandBondCollector: %d government bond series", len(records))
        return records
