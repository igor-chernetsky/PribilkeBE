import logging

import httpx

from pribilka.config import get_settings

logger = logging.getLogger(__name__)


def send_admin_telegram(message: str, *, parse_mode: str = "Markdown") -> bool:
    settings = get_settings()
    if not settings.admin_telegram_bot_token or not settings.admin_telegram_chat_id:
        return False

    url = f"https://api.telegram.org/bot{settings.admin_telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.admin_telegram_chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        response = httpx.post(url, json=payload, timeout=15.0)
        response.raise_for_status()
        return True
    except Exception:
        logger.exception("Failed to send Telegram message")
        return False
