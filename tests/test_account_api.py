from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.deps import settings_dep
from backend.queue.client import QueuedJob, QueueUnavailable
from bot.formatting import format_account_health_refresh_job


def test_account_health_refresh_route_enqueues_job(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_enqueue(*, spot_check_limit: int = 2, account_ids=None, now=None) -> QueuedJob:
        del account_ids, now
        captured["spot_check_limit"] = spot_check_limit
        return QueuedJob(id="account_health_refresh_2026050200", type="account.health_refresh")

    monkeypatch.setattr("backend.api.routes.accounts.enqueue_account_health_refresh", fake_enqueue)
    app = create_app()
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace(bot_api_token="token")
    client = TestClient(app)

    response = client.post(
        "/api/telegram-accounts/health-refresh-jobs",
        headers={"Authorization": "Bearer token"},
        json={"spot_check_limit": 3},
    )

    assert response.status_code == 202
    assert response.json() == {
        "job": {
            "id": "account_health_refresh_2026050200",
            "type": "account.health_refresh",
            "status": "queued",
        }
    }
    assert captured == {"spot_check_limit": 3}


def test_account_health_refresh_route_returns_503_when_queue_is_unavailable(monkeypatch) -> None:
    def fake_enqueue(*, spot_check_limit: int = 2, account_ids=None, now=None) -> QueuedJob:
        del spot_check_limit, account_ids, now
        raise QueueUnavailable("queue offline")

    monkeypatch.setattr("backend.api.routes.accounts.enqueue_account_health_refresh", fake_enqueue)
    app = create_app()
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace(bot_api_token="token")
    client = TestClient(app)

    response = client.post(
        "/api/telegram-accounts/health-refresh-jobs",
        headers={"Authorization": "Bearer token"},
        json={"spot_check_limit": 2},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "queue offline"}


def test_format_account_health_refresh_job_reports_job() -> None:
    message = format_account_health_refresh_job(
        {
            "job": {
                "id": "account_health_refresh_2026050200",
                "type": "account.health_refresh",
                "status": "queued",
            }
        }
    )

    assert "Account health check queued." in message
    assert "account_health_refresh_2026050200 (account.health_refresh)" in message
