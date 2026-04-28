from __future__ import annotations

import json
from typing import Any

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
            "TELEGRAM_ADMIN_USER_IDS": "123 999",
        }
    )

    assert settings.telegram_bot_token == "telegram-token"
    assert settings.api_base_url == "http://api:8000/api"
    assert settings.api_token == "api-token"
    assert settings.request_timeout_seconds == 7.5
    assert settings.allowed_user_ids == frozenset({123, 456, 789})
    assert settings.admin_user_ids == frozenset({123, 999})
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
async def test_start_snapshot_posts_window_days_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/communities/community-1/snapshot-jobs")
        assert json.loads(request.content) == {"window_days": 90}
        return httpx.Response(
            202,
            json={"job": {"id": "job-1", "type": "community.snapshot", "status": "queued"}},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.start_snapshot("community-1")
    await client.aclose()

    assert response["job"]["type"] == "community.snapshot"


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
        assert request.url.params["status"] == "approved"
        assert request.url.params["community_id"] == "community-1"
        assert request.url.params["topic_id"] == "topic-1"
        assert request.url.params["limit"] == "10"
        assert request.url.params["offset"] == "10"
        return httpx.Response(200, json={"items": [], "limit": 5, "offset": 10, "total": 0})

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.list_engagement_candidates(
        status="approved",
        community_id="community-1",
        topic_id="topic-1",
        limit=10,
        offset=10,
    )
    await client.aclose()

    assert response["offset"] == 10


@pytest.mark.asyncio
async def test_engagement_target_methods_use_target_routes() -> None:
    seen: list[tuple[str, str, dict[str, object] | None, dict[str, str]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, payload, dict(request.url.params)))
        if request.method == "GET" and request.url.path.endswith("/engagement/targets"):
            return httpx.Response(200, json={"items": [], "limit": 10, "offset": 5, "total": 0})
        if request.method == "GET":
            return httpx.Response(200, json={"id": "target-1", "status": "approved"})
        if request.method == "PATCH":
            return httpx.Response(
                200,
                json={
                    "id": "target-1",
                    "status": "approved",
                    "allow_post": True,
                },
            )
        if request.url.path.endswith("/engagement/targets"):
            return httpx.Response(201, json={"id": "target-1", "status": "pending"})
        return httpx.Response(202, json={"job": {"id": "job-1", "type": "queued"}})

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    await client.list_engagement_targets(status="approved", limit=10, offset=5)
    await client.get_engagement_target("target-1")
    await client.create_engagement_target(target_ref="@example", added_by="telegram:123")
    await client.update_engagement_target("target-1", allow_post=True, updated_by="telegram:123")
    await client.resolve_engagement_target("target-1", requested_by="telegram:123")
    await client.start_engagement_target_join("target-1", requested_by="telegram:123")
    await client.start_engagement_target_detection(
        "target-1",
        window_minutes=45,
        requested_by="telegram:123",
    )
    await client.aclose()

    assert seen[0] == (
        "GET",
        "/api/engagement/targets",
        None,
        {"limit": "10", "offset": "5", "status": "approved"},
    )
    assert seen[1] == ("GET", "/api/engagement/targets/target-1", None, {})
    assert seen[2][0:3] == (
        "POST",
        "/api/engagement/targets",
        {"target_ref": "@example", "added_by": "telegram:123"},
    )
    assert seen[3][0:3] == (
        "PATCH",
        "/api/engagement/targets/target-1",
        {"allow_post": True, "updated_by": "telegram:123"},
    )
    assert seen[4][0:3] == (
        "POST",
        "/api/engagement/targets/target-1/resolve-jobs",
        {"requested_by": "telegram:123"},
    )
    assert seen[5][1:3] == (
        "/api/engagement/targets/target-1/join-jobs",
        {"telegram_account_id": None, "requested_by": "telegram:123"},
    )
    assert seen[6][1:3] == (
        "/api/engagement/targets/target-1/detect-jobs",
        {"window_minutes": 45, "requested_by": "telegram:123"},
    )


@pytest.mark.asyncio
async def test_engagement_target_note_update_uses_target_patch_route() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/api/engagement/targets/target-1"
        assert json.loads(request.content) == {
            "notes": "Warm founder community",
            "updated_by": "telegram:123",
        }
        return httpx.Response(
            200,
            json={"id": "target-1", "status": "approved", "notes": "Warm founder community"},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.update_engagement_target(
        "target-1",
        notes="Warm founder community",
        updated_by="telegram:123",
    )
    await client.aclose()

    assert response["notes"] == "Warm founder community"


@pytest.mark.asyncio
async def test_operator_capabilities_sends_operator_header() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/operator/capabilities"
        assert request.headers["x-telegram-user-id"] == "123"
        return httpx.Response(
            200,
            json={
                "operator_user_id": 123,
                "backend_capabilities_available": True,
                "engagement_admin": True,
                "source": "backend_admin_user_ids",
            },
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.get_operator_capabilities(123)
    await client.aclose()

    assert response["engagement_admin"] is True


@pytest.mark.asyncio
async def test_admin_mutation_methods_can_send_operator_header() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/api/engagement/targets/target-1"
        assert request.headers["x-telegram-user-id"] == "123"
        assert json.loads(request.content) == {
            "allow_post": True,
            "updated_by": "telegram:123",
        }
        return httpx.Response(
            200,
            json={"id": "target-1", "status": "approved", "allow_post": True},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.update_engagement_target(
        "target-1",
        allow_post=True,
        updated_by="telegram:123",
        operator_user_id=123,
    )
    await client.aclose()

    assert response["allow_post"] is True


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
async def test_candidate_detail_revision_expire_and_retry_methods_use_candidate_routes() -> None:
    seen: list[tuple[str, str, dict[str, object] | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, payload))
        if request.url.path.endswith("/revisions"):
            return httpx.Response(200, json={"items": [], "total": 0})
        return httpx.Response(200, json={"id": "candidate-1", "status": "needs_review"})

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    await client.get_engagement_candidate("candidate-1")
    await client.list_engagement_candidate_revisions("candidate-1")
    await client.expire_engagement_candidate("candidate-1", expired_by="telegram:123")
    await client.retry_engagement_candidate("candidate-1", retried_by="telegram:123")
    await client.aclose()

    assert seen == [
        ("GET", "/api/engagement/candidates/candidate-1", None),
        ("GET", "/api/engagement/candidates/candidate-1/revisions", None),
        (
            "POST",
            "/api/engagement/candidates/candidate-1/expire",
            {"expired_by": "telegram:123"},
        ),
        (
            "POST",
            "/api/engagement/candidates/candidate-1/retry",
            {"retried_by": "telegram:123"},
        ),
    ]


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
async def test_send_engagement_candidate_posts_approved_by() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/engagement/candidates/candidate-1/send-jobs")
        assert json.loads(request.content) == {"approved_by": "telegram:123"}
        return httpx.Response(
            202,
            json={"job": {"id": "send-job", "type": "engagement.send", "status": "queued"}},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.send_engagement_candidate(
        "candidate-1",
        approved_by="telegram:123",
    )
    await client.aclose()

    assert response["job"]["type"] == "engagement.send"


@pytest.mark.asyncio
async def test_get_and_update_engagement_settings_use_community_routes() -> None:
    seen_methods: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_methods.append(request.method)
        assert request.url.path.endswith("/communities/community-1/engagement-settings")
        if request.method == "GET":
            return httpx.Response(200, json={"community_id": "community-1", "mode": "disabled"})
        assert json.loads(request.content) == {
            "mode": "require_approval",
            "allow_join": True,
            "allow_post": True,
            "reply_only": True,
            "require_approval": True,
            "max_posts_per_day": 1,
            "min_minutes_between_posts": 240,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "assigned_account_id": None,
        }
        return httpx.Response(
            200,
            json={"community_id": "community-1", "mode": "require_approval"},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    settings = await client.get_engagement_settings("community-1")
    updated = await client.update_engagement_settings(
        "community-1",
        mode="require_approval",
        allow_join=True,
        allow_post=True,
    )
    await client.aclose()

    assert settings["mode"] == "disabled"
    assert updated["mode"] == "require_approval"
    assert seen_methods == ["GET", "PUT"]


@pytest.mark.asyncio
async def test_engagement_topic_methods_use_topic_routes() -> None:
    seen: list[tuple[str, str, dict[str, object] | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, payload))
        if request.method == "GET":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(
            200 if request.method == "PATCH" else 201,
            json={
                "id": "topic-1",
                "name": "Open CRM",
                "stance_guidance": "Be useful.",
                "trigger_keywords": ["crm"],
                "active": True,
            },
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    await client.list_engagement_topics()
    await client.get_engagement_topic("topic-1")
    await client.create_engagement_topic(
        name="Open CRM",
        stance_guidance="Be useful.",
        trigger_keywords=["crm"],
    )
    await client.update_engagement_topic("topic-1", active=False)
    await client.aclose()

    assert seen[0] == ("GET", "/api/engagement/topics", None)
    assert seen[1] == ("GET", "/api/engagement/topics/topic-1", None)
    assert seen[2][0:2] == ("POST", "/api/engagement/topics")
    assert seen[2][2]["trigger_keywords"] == ["crm"]
    assert seen[3] == ("PATCH", "/api/engagement/topics/topic-1", {"active": False})


@pytest.mark.asyncio
async def test_engagement_style_rule_methods_use_style_rule_routes() -> None:
    seen: list[tuple[str, str, dict[str, object] | None, dict[str, str]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, payload, dict(request.url.params)))
        if request.method == "GET" and request.url.path.endswith("/engagement/style-rules"):
            return httpx.Response(200, json={"items": [], "limit": 5, "offset": 0, "total": 0})
        return httpx.Response(
            200 if request.method != "POST" else 201,
            json={
                "id": "rule-1",
                "scope_type": "global",
                "scope_id": None,
                "name": "Keep it brief",
                "rule_text": "Keep replies under three sentences.",
                "active": True,
                "priority": 50,
                "created_by": "operator",
                "updated_by": "operator",
                "created_at": "2026-04-21T10:00:00Z",
                "updated_at": "2026-04-21T10:00:00Z",
            },
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    await client.list_engagement_style_rules(scope_type="community", scope_id="community-1")
    await client.get_engagement_style_rule("rule-1")
    await client.create_engagement_style_rule(
        scope_type="global",
        scope_id=None,
        name="Keep it brief",
        priority=50,
        rule_text="Keep replies under three sentences.",
        created_by="telegram:123",
    )
    await client.update_engagement_style_rule(
        "rule-1",
        active=False,
        updated_by="telegram:123",
    )
    await client.aclose()

    assert seen[0] == (
        "GET",
        "/api/engagement/style-rules",
        None,
        {"limit": "5", "offset": "0", "scope_type": "community", "scope_id": "community-1"},
    )
    assert seen[1] == ("GET", "/api/engagement/style-rules/rule-1", None, {})
    assert seen[2][0:3] == (
        "POST",
        "/api/engagement/style-rules",
        {
            "scope_type": "global",
            "scope_id": None,
            "name": "Keep it brief",
            "priority": 50,
            "rule_text": "Keep replies under three sentences.",
            "created_by": "telegram:123",
        },
    )
    assert seen[3][0:3] == (
        "PATCH",
        "/api/engagement/style-rules/rule-1",
        {"active": False, "updated_by": "telegram:123"},
    )


@pytest.mark.asyncio
async def test_join_detect_and_action_methods_use_engagement_routes() -> None:
    seen: list[tuple[str, str, dict[str, object] | None, dict[str, str]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, payload, dict(request.url.params)))
        return httpx.Response(
            202 if request.method == "POST" else 200,
            json={"job": {"id": "job-1", "type": "queued"}}
            if request.method == "POST"
            else {"items": [], "limit": 5, "offset": 10, "total": 0},
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    await client.start_community_join(
        "community-1",
        telegram_account_id="account-1",
        requested_by="telegram:123",
    )
    await client.start_engagement_detection(
        "community-1",
        window_minutes=45,
        requested_by="telegram:123",
    )
    response = await client.list_engagement_actions(
        community_id="community-1",
        candidate_id="candidate-1",
        status="failed",
        action_type="reply",
        offset=10,
    )
    await client.aclose()

    assert seen[0][1] == "/api/communities/community-1/join-jobs"
    assert seen[0][2] == {
        "telegram_account_id": "account-1",
        "requested_by": "telegram:123",
    }
    assert seen[1][1] == "/api/communities/community-1/engagement-detect-jobs"
    assert seen[1][2] == {"window_minutes": 45, "requested_by": "telegram:123"}
    assert seen[2][1] == "/api/engagement/actions"
    assert seen[2][3]["candidate_id"] == "candidate-1"
    assert seen[2][3]["action_type"] == "reply"
    assert response["offset"] == 10


@pytest.mark.asyncio
async def test_get_engagement_semantic_rollout_uses_rollout_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/engagement/semantic-rollout")
        assert request.url.params["window_days"] == "21"
        assert request.url.params["community_id"] == "community-1"
        assert request.url.params["topic_id"] == "topic-1"
        return httpx.Response(
            200,
            json={
                "window_days": 21,
                "total_semantic_candidates": 0,
                "reviewed_semantic_candidates": 0,
                "pending": 0,
                "approved": 0,
                "rejected": 0,
                "expired": 0,
                "approval_rate": None,
                "bands": [],
            },
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.get_engagement_semantic_rollout(
        window_days=21,
        community_id="community-1",
        topic_id="topic-1",
    )
    await client.aclose()

    assert response["window_days"] == 21


@pytest.mark.asyncio
async def test_prompt_profile_admin_methods_use_prompt_profile_endpoints() -> None:
    seen: list[tuple[str, str, dict[str, Any] | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = None
        if request.content:
            payload = dict(json.loads(request.content.decode("utf-8")))
        seen.append((request.method, request.url.path, payload))
        if request.url.path.endswith("/versions"):
            return httpx.Response(200, json={"items": []})
        return httpx.Response(
            200,
            json={
                "id": "profile-1",
                "name": "Default",
                "description": None,
                "active": False,
                "model": "gpt-4.1-mini",
                "temperature": 0.2,
                "max_output_tokens": 1000,
                "system_prompt": "system",
                "user_prompt_template": "user",
                "output_schema_name": "engagement_detection_v1",
                "current_version_number": 1,
                "current_version_id": "version-1",
                "created_by": "operator",
                "updated_by": "operator",
                "created_at": "2026-04-21T10:00:00Z",
                "updated_at": "2026-04-21T10:00:00Z",
            },
        )

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    await client.get_engagement_prompt_profile("profile-1")
    await client.create_engagement_prompt_profile(
        name="New",
        description=None,
        active=False,
        model="gpt-4.1-mini",
        temperature=0.2,
        max_output_tokens=1000,
        system_prompt="system",
        user_prompt_template="user",
        output_schema_name="engagement_detection_v1",
        created_by="telegram:123",
    )
    await client.duplicate_engagement_prompt_profile(
        "profile-1",
        name="Copy",
        created_by="telegram:123",
    )
    await client.rollback_engagement_prompt_profile(
        "profile-1",
        version_id="version-1",
        updated_by="telegram:123",
    )
    await client.list_engagement_prompt_profile_versions("profile-1")
    await client.aclose()

    assert seen == [
        ("GET", "/api/engagement/prompt-profiles/profile-1", None),
        (
            "POST",
            "/api/engagement/prompt-profiles",
            {
                "name": "New",
                "description": None,
                "active": False,
                "model": "gpt-4.1-mini",
                "temperature": 0.2,
                "max_output_tokens": 1000,
                "system_prompt": "system",
                "user_prompt_template": "user",
                "output_schema_name": "engagement_detection_v1",
                "created_by": "telegram:123",
            },
        ),
        (
            "POST",
            "/api/engagement/prompt-profiles/profile-1/duplicate",
            {"name": "Copy", "created_by": "telegram:123"},
        ),
        (
            "POST",
            "/api/engagement/prompt-profiles/profile-1/rollback",
            {"version_id": "version-1", "updated_by": "telegram:123"},
        ),
        ("GET", "/api/engagement/prompt-profiles/profile-1/versions", None),
    ]


@pytest.mark.asyncio
async def test_engagement_cockpit_read_methods_use_task_first_routes() -> None:
    seen: list[tuple[str, str, dict[str, str] | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, dict(request.url.params)))
        return httpx.Response(200, json={"ok": True})

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    await client.get_engagement_cockpit_home()
    await client.get_engagement_cockpit_approvals()
    await client.get_engagement_cockpit_approvals_for_engagement("eng-1")
    await client.get_engagement_cockpit_issues()
    await client.get_engagement_cockpit_issues_for_engagement("eng-1")
    await client.list_engagement_cockpit_engagements(limit=5, offset=10)
    await client.get_engagement_cockpit_engagement("eng-1")
    await client.list_engagement_cockpit_sent(limit=5, offset=10)
    await client.aclose()

    assert seen == [
        ("GET", "/api/engagement/cockpit/home", {}),
        ("GET", "/api/engagement/cockpit/approvals", {}),
        ("GET", "/api/engagement/cockpit/engagements/eng-1/approvals", {}),
        ("GET", "/api/engagement/cockpit/issues", {}),
        ("GET", "/api/engagement/cockpit/engagements/eng-1/issues", {}),
        ("GET", "/api/engagement/cockpit/engagements", {"limit": "5", "offset": "10"}),
        ("GET", "/api/engagement/cockpit/engagements/eng-1", {}),
        ("GET", "/api/engagement/cockpit/sent", {"limit": "5", "offset": "10"}),
    ]


@pytest.mark.asyncio
async def test_engagement_cockpit_mutation_methods_use_semantic_routes() -> None:
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

    await client.approve_engagement_cockpit_draft("draft-1")
    await client.reject_engagement_cockpit_draft("draft-1")
    await client.edit_engagement_cockpit_draft(
        "draft-1",
        edit_request="Make it shorter",
        requested_by="telegram:123",
    )
    await client.act_on_engagement_cockpit_issue("issue-1", action_key="quiet")
    await client.get_engagement_cockpit_issue_rate_limit("issue-1")
    await client.aclose()

    assert seen == [
        ("POST", "/api/engagement/cockpit/drafts/draft-1/approve", None),
        ("POST", "/api/engagement/cockpit/drafts/draft-1/reject", None),
        (
            "POST",
            "/api/engagement/cockpit/drafts/draft-1/edit",
            {"edit_request": "Make it shorter", "requested_by": "telegram:123"},
        ),
        ("POST", "/api/engagement/cockpit/issues/issue-1/actions/quiet", None),
        ("GET", "/api/engagement/cockpit/issues/issue-1/rate-limit", None),
    ]


@pytest.mark.asyncio
async def test_engagement_cockpit_quiet_hours_methods_use_expected_payloads() -> None:
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

    await client.get_engagement_cockpit_quiet_hours("eng-1")
    await client.update_engagement_cockpit_quiet_hours(
        "eng-1",
        quiet_hours_enabled=True,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
    )
    await client.update_engagement_cockpit_quiet_hours(
        "eng-1",
        quiet_hours_enabled=False,
    )
    await client.aclose()

    assert seen == [
        ("GET", "/api/engagement/cockpit/engagements/eng-1/quiet-hours", None),
        (
            "PUT",
            "/api/engagement/cockpit/engagements/eng-1/quiet-hours",
            {
                "quiet_hours_enabled": True,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "07:00",
            },
        ),
        (
            "PUT",
            "/api/engagement/cockpit/engagements/eng-1/quiet-hours",
            {"quiet_hours_enabled": False},
        ),
    ]


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
