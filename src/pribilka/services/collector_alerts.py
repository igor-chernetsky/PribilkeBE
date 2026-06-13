import logging
from datetime import UTC, datetime

import httpx

from pribilka.collectors.pl.deposits.parse_result import ParseStatus, ParserResult
from pribilka.config import get_settings
from pribilka.services.redis_client import get_redis
from pribilka.services.telegram import send_admin_telegram

logger = logging.getLogger(__name__)

ALERT_KEY_PREFIX = "collector_alert"


def report_deposit_parse_results(results: list[ParserResult], total_records: int) -> None:
    """Notify admin when parsers fail or return no data."""
    problems = [
        r
        for r in results
        if r.status == ParseStatus.ERROR
        or (r.status == ParseStatus.EMPTY and r.alert_on_empty)
    ]
    if not problems and total_records > 0:
        return

    if total_records == 0 and not problems:
        problems = results

    lines = ["⚠️ *Pribilka — problem z kolektorem depozytów*"]
    for result in problems:
        if result.status == ParseStatus.ERROR:
            lines.append(
                f"• *{result.institution_name}* (`{result.parser_name}`): błąd parsowania\n"
                f"  `{result.error_message or 'unknown'}`"
            )
        elif result.status == ParseStatus.EMPTY:
            lines.append(
                f"• *{result.institution_name}* (`{result.parser_name}`): 0 ofert "
                f"(możliwa zmiana layoutu strony)"
            )

    if total_records == 0:
        lines.append(f"\nŁącznie zapisano *0* depozytów po tym przebiegu.")

    lines.append(f"\n_{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}_")
    _send_with_cooldown("\n".join(lines), alert_key="deposit_collector_summary")


def _send_with_cooldown(message: str, alert_key: str) -> None:
    settings = get_settings()
    cooldown_seconds = settings.collector_alert_cooldown_hours * 3600
    redis_key = f"{ALERT_KEY_PREFIX}:{alert_key}"

    try:
        redis_client = get_redis()
        if redis_client.get(redis_key):
            logger.info("Collector alert suppressed (cooldown): %s", alert_key)
            return
    except Exception:
        logger.exception("Redis unavailable for alert cooldown")

    sent = send_admin_telegram(message) or _send_webhook(message)
    if not sent:
        logger.warning("Collector alert not delivered — configure Telegram or webhook:\n%s", message)
        return

    try:
        redis_client = get_redis()
        redis_client.setex(redis_key, cooldown_seconds, "1")
    except Exception:
        logger.exception("Failed to set alert cooldown in Redis")


def _send_webhook(message: str) -> bool:
    settings = get_settings()
    if not settings.admin_webhook_url:
        return False

    try:
        response = httpx.post(
            settings.admin_webhook_url,
            json={"text": message, "source": "pribilka-collector"},
            timeout=15.0,
        )
        response.raise_for_status()
        return True
    except Exception:
        logger.exception("Failed to send webhook alert")
        return False
