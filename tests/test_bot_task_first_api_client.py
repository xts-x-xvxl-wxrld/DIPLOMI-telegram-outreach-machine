from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from bot.api_client import BotApiClient


@pytest.mark.asyncio
async def test_engagement_wizard_methods_use_task_first_routes() -> None:
    seen: list[tuple[str, str, dict[str, Any] | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, payload))
        return httpx.Response(200, json={"ok": True})

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    await client.create_engagement(target_id="target-1", created_by="telegram:123")
    await client.patch_engagement("eng-1", topic_id="topic-1", name="HSE Live")
    await client.put_engagement_settings(
        "eng-1",
        assigned_account_id="acct-1",
        mode="suggest",
    )
    await client.wizard_confirm_engagement("eng-1", requested_by="telegram:123")
    await client.wizard_retry_engagement("eng-1")
    await client.aclose()

    assert seen == [
        (
            "POST",
            "/api/engagements",
            {"target_id": "target-1", "created_by": "telegram:123"},
        ),
        (
            "PATCH",
            "/api/engagements/eng-1",
            {"topic_id": "topic-1", "name": "HSE Live"},
        ),
        (
            "PUT",
            "/api/engagements/eng-1/settings",
            {"assigned_account_id": "acct-1", "mode": "suggest"},
        ),
        (
            "POST",
            "/api/engagements/eng-1/wizard-confirm",
            {"requested_by": "telegram:123"},
        ),
        ("POST", "/api/engagements/eng-1/wizard-retry", {}),
    ]
