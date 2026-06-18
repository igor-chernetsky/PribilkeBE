import logging
import time
from datetime import timedelta

import httpx

from pribilka.collectors.pl.deposits.http import is_bot_wall
from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.collectors.pl.rental.cities import POLAND_RENTAL_CITIES, TRACKED_ROOM_COUNTS
from pribilka.collectors.pl.rental.issues import RentalCollectorIssue, RentalCollectorIssueKind
from pribilka.collectors.pl.rental.otodom import (
    SEGMENT_REQUEST_DELAY_SEC,
    build_otodom_search_url,
    create_otodom_client,
    fetch_otodom_search_items,
    warm_otodom_session,
)
from pribilka.models.enums import AssetClass, CountryCode, RentalListingType
from pribilka.services.collector_alerts import report_rental_collector_issues

logger = logging.getLogger(__name__)


class PolandRentalCollector(BaseCollector):
    def __init__(self, *, max_pages: int = 2):
        super().__init__(
            CollectorConfig(
                asset_class=AssetClass.BANK_DEPOSIT,
                country=CountryCode.PL,
                source_name="poland_rental_otodom",
                refresh_interval=timedelta(hours=12),
            )
        )
        self.max_pages = max_pages
        self._last_issues: list[RentalCollectorIssue] = []

    @property
    def last_issues(self) -> list[RentalCollectorIssue]:
        return self._last_issues

    def collect(self) -> list[dict]:
        records: list[dict] = []
        issues: list[RentalCollectorIssue] = []
        with create_otodom_client() as client:
            warm_otodom_session(client)
            for city in POLAND_RENTAL_CITIES:
                for room_count in TRACKED_ROOM_COUNTS:
                    for listing_type in (RentalListingType.SALE, RentalListingType.RENT):
                        segment_records, segment_issues = self._collect_segment(
                            city_slug=city.otodom_slug,
                            location_path=city.otodom_location_path,
                            listing_type=listing_type,
                            room_count=room_count,
                            client=client,
                        )
                        records.extend(segment_records)
                        issues.extend(segment_issues)
                        time.sleep(SEGMENT_REQUEST_DELAY_SEC)

        self._last_issues = issues
        report_rental_collector_issues(issues, total_records=len(records))
        logger.info("Collected %d rental listings (%d issues)", len(records), len(issues))
        return records

    def _collect_segment(
        self,
        *,
        city_slug: str,
        location_path: str,
        listing_type: RentalListingType,
        room_count: int,
        client: httpx.Client,
    ) -> tuple[list[dict], list[RentalCollectorIssue]]:
        segment: list[dict] = []
        issues: list[RentalCollectorIssue] = []
        for page in range(1, self.max_pages + 1):
            url = build_otodom_search_url(
                location_path=location_path,
                listing_type=listing_type,
                room_count=room_count,
                page=page,
            )
            try:
                parsed, html = fetch_otodom_search_items(
                    url,
                    city_slug=city_slug,
                    listing_type=listing_type,
                    room_count=room_count,
                    client=client,
                )
            except Exception as exc:
                logger.warning(
                    "Otodom fetch failed city=%s type=%s rooms=%s page=%s: %s",
                    city_slug,
                    listing_type.value,
                    room_count,
                    page,
                    exc,
                )
                if page == 1 or not segment:
                    issues.append(
                        RentalCollectorIssue(
                            city_slug=city_slug,
                            listing_type=listing_type.value,
                            room_count=room_count,
                            page=page,
                            url=url,
                            kind=RentalCollectorIssueKind.FETCH_ERROR,
                            error_message=str(exc),
                        )
                    )
                break

            if not parsed:
                kind = (
                    RentalCollectorIssueKind.BOT_WALL
                    if is_bot_wall(html)
                    else RentalCollectorIssueKind.EMPTY_PARSE
                )
                if page == 1:
                    issues.append(
                        RentalCollectorIssue(
                            city_slug=city_slug,
                            listing_type=listing_type.value,
                            room_count=room_count,
                            page=page,
                            url=url,
                            kind=kind,
                            error_message="No listings parsed from Otodom response",
                        )
                    )
                break
            segment.extend(parsed)
        return segment, issues
