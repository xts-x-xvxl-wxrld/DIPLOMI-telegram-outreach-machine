from __future__ import annotations

import httpx
import pytest

from bot.api_client import BotApiClient


@pytest.mark.asyncio
async def test_search_api_client_posts_search_run_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/search-runs")
        assert request.method == "POST"
        payload = request.read()
        assert b"Hungarian SaaS" in payload
        assert b"telegram_entity_search" in payload
        return httpx.Response(
            201,
            json={
                "search_run": {"id": "run-1", "raw_query": "Hungarian SaaS"},
                "job": {"id": "job-1", "type": "search.plan", "status": "queued"},
            },
        )

    client = BotApiClient(
        base_url="http://api.local/api",
        api_token="token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.create_search_run("Hungarian SaaS", requested_by="telegram:123")

    assert response["job"]["type"] == "search.plan"
    await client.aclose()


@pytest.mark.asyncio
async def test_search_api_client_converts_candidate_to_seed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/search-candidates/cand-1/convert-to-seed")
        assert request.method == "POST"
        payload = request.read()
        assert b"Search: Hungarian SaaS" in payload
        return httpx.Response(
            200,
            json={
                "seed_group": {"id": "sg-1", "name": "Search: Hungarian SaaS"},
                "seed_channel": {"id": "seed-1", "telegram_url": "https://t.me/husaas"},
                "candidate": {"id": "cand-1", "status": "converted_to_seed"},
                "review": {"id": "review-1", "action": "convert_to_seed"},
            },
        )

    client = BotApiClient(
        base_url="http://api.local/api",
        api_token="token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.convert_search_candidate_to_seed(
        "cand-1",
        seed_group_name="Search: Hungarian SaaS",
        requested_by="telegram:123",
    )

    assert response["candidate"]["status"] == "converted_to_seed"
    await client.aclose()
