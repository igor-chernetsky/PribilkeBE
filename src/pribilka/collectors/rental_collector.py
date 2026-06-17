import logging
from datetime import timedelta

from pribilka.collectors.pl.deposits.http import is_bot_wall
from pribilka.collectors.base import BaseCollector, CollectorConfig
from pribilka.collectors.pl.rental.cities import POLAND_RENTAL_CITIES, TRACKED_ROOM_COUNTS
from pribilka.collectors.pl.rental.issues import RentalCollectorIssue, RentalCollectorIssueKind
from pribilka.collectors.pl.rental.otodom import (
    build_otodom_search_url,
    fetch_otodom_search_html,
    parse_otodom_search_html,
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
        for city in POLAND_RENTAL_CITIES:
            for room_count in TRACKED_ROOM_COUNTS:
                for listing_type in (RentalListingType.SALE, RentalListingType.RENT):
                    segment_records, segment_issues = self._collect_segment(
                        city_slug=city.otodom_slug,
                        listing_type=listing_type,
                        room_count=room_count,
                    )
                    records.extend(segment_records)
                    issues.extend(segment_issues)

        self._last_issues = issues
        report_rental_collector_issues(issues, total_records=len(records))
        logger.info("Collected %d rental listings (%d issues)", len(records), len(issues))
        return records

    def _collect_segment(
        self,
        *,
        city_slug: str,
        listing_type: RentalListingType,
        room_count: int,
    ) -> tuple[list[dict], list[RentalCollectorIssue]]:
        segment: list[dict] = []
        issues: list[RentalCollectorIssue] = []
        for page in range(1, self.max_pages + 1):
            url = build_otodom_search_url(
                city_slug=city_slug,
                listing_type=listing_type,
                room_count=room_count,
                page=page,
            )
            try:
                html = fetch_otodom_search_html(url)
            except Exception as exc:
                logger.warning(
                    "Otodom fetch failed city=%s type=%s rooms=%s page=%s: %s",
                    city_slug,
                    listing_type.value,
                    room_count,
                    page,
                    exc,
                )
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

            parsed = parse_otodom_search_html(
                html,
                city_slug=city_slug,
                listing_type=listing_type,
                room_count=room_count,
            )
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
