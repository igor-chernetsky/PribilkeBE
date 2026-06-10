import json
import logging

import httpx

from pribilka.config import get_settings

logger = logging.getLogger(__name__)

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


def _get_access_token() -> str | None:
    settings = get_settings()
    if not settings.firebase_credentials_json:
        return None

    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests

        info = json.loads(settings.firebase_credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=[_FCM_SCOPE]
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        return credentials.token
    except Exception:
        logger.exception("Failed to obtain Firebase access token")
        return None


def send_push(token: str, title: str, body: str, data: dict[str, str] | None = None) -> bool:
    settings = get_settings()
    if not settings.firebase_project_id:
        logger.debug("FCM skipped — firebase_project_id not configured")
        return False

    access_token = _get_access_token()
    if not access_token:
        return False

    message: dict = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
        }
    }
    if data:
        message["message"]["data"] = data

    url = (
        f"https://fcm.googleapis.com/v1/projects/{settings.firebase_project_id}/messages:send"
    )

    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=message,
            timeout=15,
        )
        if response.status_code >= 400:
            logger.warning("FCM error %s: %s", response.status_code, response.text)
            return False
        return True
    except Exception:
        logger.exception("FCM send failed")
        return False


def send_push_to_user(
    db, user_id: str, title: str, body: str, data: dict[str, str] | None = None
) -> int:
    from sqlalchemy import select

    from pribilka.models.device_token import DeviceToken

    tokens = db.scalars(
        select(DeviceToken).where(
            DeviceToken.user_id == user_id,
            DeviceToken.push_enabled.is_(True),
        )
    ).all()

    sent = 0
    for device in tokens:
        if send_push(device.token, title, body, data):
            sent += 1
    return sent
