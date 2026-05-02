from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from bot.api_client import BotApiClient


@pytest.mark.asyncio
async def test_account_onboarding_methods_use_account_routes() -> None:
    seen: list[tuple[str, str, dict[str, Any]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append((request.method, request.url.path, payload))
        if request.url.path.endswith("/start"):
            return httpx.Response(
                200,
                json={
                    "status": "code_sent",
                    "account_pool": payload["account_pool"],
                    "phone": payload["phone"],
                    "session_file_name": payload["session_name"],
                    "phone_code_hash": "hash-1",
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "registered",
                "account_pool": payload["account_pool"],
                "phone": payload["phone"],
                "session_file_name": payload["session_name"],
            },
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    await client.start_account_onboarding(
        account_pool="search",
        phone="+10000000000",
        session_name="research-1.session",
        notes="warm spare",
        requested_by="telegram:123",
    )
    await client.complete_account_onboarding(
        account_pool="search",
        phone="+10000000000",
        session_name="research-1.session",
        phone_code_hash="hash-1",
        code="12345",
        requested_by="telegram:123",
    )
    await client.aclose()

    assert seen == [
        (
            "POST",
            "/api/telegram-accounts/onboarding/start",
            {
                "account_pool": "search",
                "phone": "+10000000000",
                "session_name": "research-1.session",
                "notes": "warm spare",
                "requested_by": "telegram:123",
            },
        ),
        (
            "POST",
            "/api/telegram-accounts/onboarding/complete",
            {
                "account_pool": "search",
                "phone": "+10000000000",
                "session_name": "research-1.session",
                "phone_code_hash": "hash-1",
                "code": "12345",
                "password": None,
                "notes": None,
                "requested_by": "telegram:123",
            },
        ),
    ]


@pytest.mark.asyncio
async def test_account_health_refresh_method_uses_account_route() -> None:
    seen: list[tuple[str, str, dict[str, Any]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append((request.method, request.url.path, payload))
        return httpx.Response(
            202,
            json={
                "job": {
                    "id": "account_health_refresh_2026050200",
                    "type": "account.health_refresh",
                    "status": "queued",
                }
            },
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.start_account_health_refresh(spot_check_limit=3)
    await client.aclose()

    assert response == {
        "job": {
            "id": "account_health_refresh_2026050200",
            "type": "account.health_refresh",
            "status": "queued",
        }
    }
    assert seen == [
        (
            "POST",
            "/api/telegram-accounts/health-refresh-jobs",
            {"spot_check_limit": 3},
        )
    ]
