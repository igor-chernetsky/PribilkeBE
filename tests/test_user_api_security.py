from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pribilka.db.base import Base
from pribilka.db.session import get_db
from pribilka.main import app
from pribilka.models.device_token import DeviceToken
from pribilka.models.notification import Notification
from pribilka.models.user_access_token import UserAccessToken
from pribilka.models.user_alert import UserAlert

_SECURITY_TABLES = (
    UserAccessToken.__table__,
    UserAlert.__table__,
    Notification.__table__,
    DeviceToken.__table__,
)


def _create_security_tables(engine):
    Base.metadata.create_all(bind=engine, tables=list(_SECURITY_TABLES))


def _make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_security_tables(engine)
    session_local = sessionmaker(bind=engine)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client, session_local


def _bootstrap(client: TestClient, user_id: str) -> str:
    response = client.post("/api/v1/auth/bootstrap", json={"user_id": user_id})
    assert response.status_code == 200
    data = response.json()
    assert data["issued"] is True
    return data["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@patch("pribilka.api.v1.auth.limiter.enabled", False)
@patch("pribilka.api.v1.alerts.limiter.enabled", False)
@patch("pribilka.api.v1.notifications.limiter.enabled", False)
@patch("pribilka.api.v1.devices.limiter.enabled", False)
def test_bootstrap_and_user_endpoints_require_token():
    client, session_local = _make_client()
    user_a = "user-a-0001"
    user_b = "user-b-0001"
    token_a = _bootstrap(client, user_a)

    denied = client.post("/api/v1/auth/bootstrap", json={"user_id": user_a})
    assert denied.status_code == 401

    refresh = client.post(
        "/api/v1/auth/bootstrap",
        json={"user_id": user_a},
        headers=_auth_headers(token_a),
    )
    assert refresh.status_code == 200
    assert refresh.json()["issued"] is False

    assert client.get("/api/v1/alerts").status_code == 401

    create = client.post(
        "/api/v1/alerts",
        headers=_auth_headers(token_a),
        json={"name": "My alert", "country": "PL", "currency": "PLN"},
    )
    assert create.status_code == 201
    alert_id = create.json()["id"]

    token_b = _bootstrap(client, user_b)
    forbidden = client.put(
        f"/api/v1/alerts/{alert_id}",
        headers=_auth_headers(token_b),
        json={"name": "Hijacked"},
    )
    assert forbidden.status_code == 404

    db = session_local()
    try:
        notif = Notification(
            user_id=user_a,
            title="Test",
            message="Hello",
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)

        mark = client.post(
            "/api/v1/notifications/read",
            headers=_auth_headers(token_b),
            json={"notification_ids": [str(notif.id)]},
        )
        assert mark.status_code == 403

        device = DeviceToken(
            user_id=user_a,
            token="fcm-token-user-a",
            platform="ios",
            push_enabled=True,
        )
        db.add(device)
        db.commit()

        hijack = client.post(
            "/api/v1/devices/register",
            headers=_auth_headers(token_b),
            json={
                "token": "fcm-token-user-a",
                "platform": "android",
                "push_enabled": True,
            },
        )
        assert hijack.status_code == 403
    finally:
        db.close()

    app.dependency_overrides.clear()


@patch("pribilka.services.device_auth.secrets.token_urlsafe", return_value="known-token-value")
def test_device_auth_service_roundtrip(_mock_token):
    from pribilka.services.device_auth import hash_access_token, issue_access_token, resolve_user_id

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_security_tables(engine)
    session_local = sessionmaker(bind=engine)
    db = session_local()

    raw = issue_access_token(db, "user-1")
    db.commit()
    assert raw == "known-token-value"
    assert resolve_user_id(db, raw) == "user-1"
    assert hash_access_token(raw) == hash_access_token("known-token-value")

    db.close()
