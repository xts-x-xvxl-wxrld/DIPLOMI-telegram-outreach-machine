from __future__ import annotations

import json

import httpx
import pytest

from bot.api_client import BotApiClient, BotApiError
from bot.config import load_settings, parse_allowed_user_ids, validate_runtime_settings


def test_load_bot_settings_from_env_mapping() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "telegram-token",
            "BOT_API_BASE_URL": "http://api:8000/api/",
            "BOT_API_TOKEN": "api-token",
            "BOT_API_TIMEOUT_SECONDS": "7.5",
            "TELEGRAM_ALLOWED_USER_IDS": "123, 456 789",
        }
    )

    assert settings.telegram_bot_token == "telegram-token"
    assert settings.api_base_url == "http://api:8000/api"
    assert settings.api_token == "api-token"
    assert settings.request_timeout_seconds == 7.5
    assert settings.allowed_user_ids == frozenset({123, 456, 789})
    validate_runtime_settings(settings)


def test_parse_allowed_user_ids_rejects_non_numeric_values() -> None:
    with pytest.raises(ValueError, match="numeric Telegram user IDs"):
        parse_allowed_user_ids("123,not-a-number")


@pytest.mark.asyncio
async def test_create_brief_sends_auth_and_auto_start_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/briefs")
        assert request.headers["authorization"] == "Bearer api-token"
        assert json.loads(request.content) == {
            "raw_input": "Hungarian SaaS founders",
            "auto_start_discovery": True,
        }
        return httpx.Response(
            201,
            json={
                "brief": {"id": "brief-1"},
                "job": {"id": "job-1", "type": "brief.process", "status": "queued"},
            },
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.create_brief("Hungarian SaaS founders")
    await client.aclose()

    assert response["job"]["type"] == "brief.process"


@pytest.mark.asyncio
async def test_import_seed_csv_posts_csv_text() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/seed-imports/csv")
        assert request.headers["authorization"] == "Bearer api-token"
        payload = json.loads(request.content)
        assert payload["csv_text"] == "group_name,channel\nSaaS,@founders\n"
        assert payload["file_name"] == "seeds.csv"
        assert payload["requested_by"] == "telegram_bot"
        return httpx.Response(
            201,
            json={"imported": 1, "updated": 0, "errors": [], "groups": []},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.import_seed_csv(
        "group_name,channel\nSaaS,@founders\n",
        file_name="seeds.csv",
    )
    await client.aclose()

    assert response["imported"] == 1


@pytest.mark.asyncio
async def test_submit_telegram_entity_posts_handle() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/telegram-entities")
        assert request.headers["authorization"] == "Bearer api-token"
        assert json.loads(request.content) == {
            "handle": "@example",
            "requested_by": "telegram_bot",
        }
        return httpx.Response(
            202,
            json={
                "intake": {
                    "id": "intake-1",
                    "telegram_url": "https://t.me/example",
                    "status": "pending",
                },
                "job": {
                    "id": "job-1",
                    "type": "telegram_entity.resolve",
                    "status": "queued",
                },
            },
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.submit_telegram_entity("@example")
    await client.aclose()

    assert response["job"]["type"] == "telegram_entity.resolve"


@pytest.mark.asyncio
async def test_start_seed_group_resolution_posts_contract_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/seed-groups/group-1/resolve-jobs")
        assert request.headers["authorization"] == "Bearer api-token"
        assert json.loads(request.content) == {"limit": 100, "retry_failed": False}
        return httpx.Response(
            202,
            json={"job": {"id": "job-1", "type": "seed.resolve", "status": "queued"}},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.start_seed_group_resolution("group-1")
    await client.aclose()

    assert response["job"]["type"] == "seed.resolve"


@pytest.mark.asyncio
async def test_get_seed_group_uses_detail_route() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/seed-groups/group-1")
        return httpx.Response(
            200,
            json={"group": {"id": "group-1", "name": "SaaS Hungary", "seed_count": 2}},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.get_seed_group("group-1")
    await client.aclose()

    assert response["group"]["name"] == "SaaS Hungary"


@pytest.mark.asyncio
async def test_list_seed_group_candidates_uses_seed_group_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/seed-groups/group-1/candidates")
        assert request.url.params["status"] == "candidate"
        assert request.url.params["limit"] == "5"
        assert request.url.params["offset"] == "10"
        return httpx.Response(200, json={"items": [], "limit": 5, "offset": 10, "total": 0})

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.list_seed_group_candidates("group-1", offset=10)
    await client.aclose()

    assert response["offset"] == 10


@pytest.mark.asyncio
async def test_start_seed_group_expansion_posts_contract_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/seed-groups/group-1/expansion-jobs")
        assert request.headers["authorization"] == "Bearer api-token"
        assert json.loads(request.content) == {"brief_id": "brief-1", "depth": 1}
        return httpx.Response(
            202,
            json={"job": {"id": "job-1", "type": "seed.expand", "status": "queued"}},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.start_seed_group_expansion("group-1", brief_id="brief-1")
    await client.aclose()

    assert response["job"]["type"] == "seed.expand"


@pytest.mark.asyncio
async def test_start_collection_posts_window_days_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/communities/community-1/collection-jobs")
        assert json.loads(request.content) == {"window_days": 90}
        return httpx.Response(
            202,
            json={"job": {"id": "job-1", "type": "collection.run", "status": "queued"}},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.start_collection("community-1")
    await client.aclose()

    assert response["job"]["type"] == "collection.run"


@pytest.mark.asyncio
async def test_list_community_members_uses_safe_member_endpoint_filters() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/communities/community-1/members")
        assert request.url.params["limit"] == "10"
        assert request.url.params["offset"] == "20"
        assert request.url.params["username_present"] == "true"
        assert request.url.params["activity_status"] == "active"
        return httpx.Response(200, json={"items": [], "limit": 10, "offset": 20, "total": 0})

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.list_community_members(
        "community-1",
        limit=10,
        offset=20,
        username_present=True,
        activity_status="active",
    )
    await client.aclose()

    assert response["total"] == 0


@pytest.mark.asyncio
async def test_list_engagement_candidates_uses_review_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/engagement/candidates")
        assert request.url.params["status"] == "needs_review"
        assert request.url.params["limit"] == "5"
        assert request.url.params["offset"] == "10"
        return httpx.Response(200, json={"items": [], "limit": 5, "offset": 10, "total": 0})

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.list_engagement_candidates(offset=10)
    await client.aclose()

    assert response["offset"] == 10


@pytest.mark.asyncio
async def test_approve_engagement_candidate_posts_reviewer() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/engagement/candidates/candidate-1/approve")
        assert json.loads(request.content) == {"reviewed_by": "telegram:123"}
        return httpx.Response(
            200,
            json={"id": "candidate-1", "status": "approved", "reviewed_by": "telegram:123"},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.approve_engagement_candidate(
        "candidate-1",
        reviewed_by="telegram:123",
    )
    await client.aclose()

    assert response["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_engagement_candidate_posts_reviewer() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/engagement/candidates/candidate-1/reject")
        assert json.loads(request.content) == {"reviewed_by": "telegram:123"}
        return httpx.Response(
            200,
            json={"id": "candidate-1", "status": "rejected", "reviewed_by": "telegram:123"},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.reject_engagement_candidate(
        "candidate-1",
        reviewed_by="telegram:123",
    )
    await client.aclose()

    assert response["status"] == "rejected"


@pytest.mark.asyncio
async def test_api_error_uses_fastapi_detail_message() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": {"message": "Job not found"}})

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BotApiError, match="Job not found") as exc_info:
        await client.get_job("missing-job")
    await client.aclose()

    assert exc_info.value.status_code == 404
