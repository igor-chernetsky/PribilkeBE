from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from pribilka.config import get_settings
from pribilka.main import app
from pribilka.services.collector_status import save_collector_run


@patch("pribilka.api.admin_deps.get_settings")
def test_collector_status_requires_api_key(mock_settings):
    mock_settings.return_value = MagicMock(admin_api_key="secret-key")
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.get("/api/v1/admin/collector-status")
    assert response.status_code == 401

    response = client.get(
        "/api/v1/admin/collector-status",
        headers={"X-Admin-Api-Key": "wrong"},
    )
    assert response.status_code == 401

    get_settings.cache_clear()


@patch("pribilka.api.v1.admin.list_collector_statuses")
@patch("pribilka.api.admin_deps.get_settings")
def test_collector_status_returns_snapshots(mock_settings, mock_list):
    mock_settings.return_value = MagicMock(admin_api_key="secret-key")
    get_settings.cache_clear()

    mock_list.return_value = [
        {
            "collector_key": "deposit",
            "source_name": "poland_deposits",
            "status": "ok",
            "records_collected": 12,
            "ingested_count": 12,
            "finished_at": "2026-06-08T10:00:00+00:00",
            "duration_ms": 4500,
            "error_message": None,
            "parsers": [
                {
                    "parser_name": "IngDepositParser",
                    "institution_name": "ING Bank Śląski",
                    "status": "ok",
                    "offer_count": 5,
                    "error_message": None,
                    "alert_on_empty": True,
                }
            ],
        }
    ]

    client = TestClient(app)
    response = client.get(
        "/api/v1/admin/collector-status",
        headers={"X-Admin-Api-Key": "secret-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["collectors"]) == 1
    assert data["collectors"][0]["collector_key"] == "deposit"
    assert data["collectors"][0]["parsers"][0]["offer_count"] == 5

    get_settings.cache_clear()


@patch("pribilka.services.collector_status.get_redis")
def test_save_collector_run_persists_to_redis(mock_get_redis):
    redis_mock = MagicMock()
    mock_get_redis.return_value = redis_mock

    save_collector_run(
        collector_key="bond",
        source_name="poland_bonds",
        status="ok",
        records_collected=8,
        ingested_count=8,
        duration_ms=1200,
    )

    redis_mock.setex.assert_called_once()
    key, ttl, payload = redis_mock.setex.call_args[0]
    assert key == "collector:status:bond"
    assert ttl == 7 * 24 * 3600
    assert '"collector_key": "bond"' in payload or '"collector_key":"bond"' in payload.replace(" ", "")
