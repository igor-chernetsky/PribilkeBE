import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from pribilka.collectors.pl.deposits.parse_result import ParserResult
from pribilka.services.redis_client import get_redis

logger = logging.getLogger(__name__)

STATUS_KEY_PREFIX = "collector:status"
STATUS_TTL_SECONDS = 7 * 24 * 3600  # 7 days

COLLECTOR_KEYS = ("deposit", "bond", "fx", "gold")


@dataclass
class CollectorRunSnapshot:
    collector_key: str
    source_name: str
    status: str
    records_collected: int
    ingested_count: int
    finished_at: str
    duration_ms: int
    error_message: str | None = None
    parsers: list[dict] = field(default_factory=list)


def _status_key(collector_key: str) -> str:
    return f"{STATUS_KEY_PREFIX}:{collector_key}"


def _serialize_parser_result(result: ParserResult) -> dict:
    return {
        "parser_name": result.parser_name,
        "institution_name": result.institution_name,
        "status": result.status.value,
        "offer_count": result.offer_count,
        "error_message": result.error_message,
        "alert_on_empty": result.alert_on_empty,
    }


def save_collector_run(
    *,
    collector_key: str,
    source_name: str,
    status: str,
    records_collected: int,
    ingested_count: int,
    duration_ms: int,
    error_message: str | None = None,
    parser_results: list[ParserResult] | None = None,
) -> None:
    snapshot = CollectorRunSnapshot(
        collector_key=collector_key,
        source_name=source_name,
        status=status,
        records_collected=records_collected,
        ingested_count=ingested_count,
        finished_at=datetime.now(UTC).isoformat(),
        duration_ms=duration_ms,
        error_message=error_message,
        parsers=[_serialize_parser_result(r) for r in (parser_results or [])],
    )

    try:
        redis_client = get_redis()
        redis_client.setex(
            _status_key(collector_key),
            STATUS_TTL_SECONDS,
            json.dumps(asdict(snapshot)),
        )
    except Exception:
        logger.exception("Failed to persist collector status for %s", collector_key)


def get_collector_status(collector_key: str) -> dict | None:
    try:
        redis_client = get_redis()
        raw = redis_client.get(_status_key(collector_key))
    except Exception:
        logger.exception("Redis unavailable while reading collector status")
        return None

    if not raw:
        return None

    return json.loads(raw)


def list_collector_statuses() -> list[dict]:
    statuses: list[dict] = []
    for key in COLLECTOR_KEYS:
        snapshot = get_collector_status(key)
        if snapshot:
            statuses.append(snapshot)
    return statuses
