from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from backend.api.routes.engagement import (
    get_engagement_target_collection_runs,
    post_engagement_target_collection_job,
)
from backend.api.schemas import EngagementCollectionJobRequest
from backend.db.enums import (
    AnalysisStatus,
    CollectionRunStatus,
    CommunityStatus,
    EngagementTargetRefType,
    EngagementTargetStatus,
)
from backend.db.models import CollectionRun, Community, EngagementTarget
from backend.queue.client import QueuedJob
from bot.api_client import BotApiClient
from bot.engagement_commands_admin import target_collect_command, target_collection_runs_command
from bot.formatting import format_engagement_candidate_card, format_engagement_target_card
from bot.ui import (
    ACTION_ENGAGEMENT_TARGET_COLLECT,
    ACTION_ENGAGEMENT_TARGET_COLLECTION_RUNS,
    parse_callback_data,
)


@pytest.mark.asyncio
async def test_target_collection_job_requires_approved_detect_target(monkeypatch) -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    db = FakeDb(target=target)
    captured: dict[str, object] = {}

    def fake_enqueue(
        community_id_arg: object,
        *,
        reason: str,
        requested_by: str | None,
        window_days: int,
    ) -> QueuedJob:
        captured.update(
            {
                "community_id": community_id_arg,
                "reason": reason,
                "requested_by": requested_by,
                "window_days": window_days,
            }
        )
        return QueuedJob(id="collection-job", type="collection.run")

    monkeypatch.setattr("backend.api.routes.engagement.enqueue_collection", fake_enqueue)

    response = await post_engagement_target_collection_job(
        target.id,
        EngagementCollectionJobRequest(window_days=30, requested_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.job.id == "collection-job"
    assert captured == {
        "community_id": community_id,
        "reason": "engagement",
        "requested_by": "telegram:123",
        "window_days": 30,
    }


@pytest.mark.asyncio
async def test_target_collection_job_rejects_unapproved_target() -> None:
    target = _target(uuid4(), status=EngagementTargetStatus.RESOLVED.value)
    db = FakeDb(target=target)

    with pytest.raises(HTTPException) as exc_info:
        await post_engagement_target_collection_job(
            target.id,
            EngagementCollectionJobRequest(requested_by="telegram:123"),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "target_not_approved"


@pytest.mark.asyncio
async def test_target_collection_runs_returns_recent_runs() -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    run = CollectionRun(
        id=uuid4(),
        community_id=community_id,
        status=CollectionRunStatus.COMPLETED.value,
        analysis_status=AnalysisStatus.SKIPPED.value,
        window_days=90,
        messages_seen=3,
        members_seen=2,
        activity_events=2,
        started_at=datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 4, 22, 10, 1, tzinfo=timezone.utc),
    )
    db = FakeDb(target=target, collection_runs=[run])

    response = await get_engagement_target_collection_runs(target.id, db)  # type: ignore[arg-type]

    assert response.items[0].id == run.id
    assert response.items[0].messages_seen == 3


@pytest.mark.asyncio
async def test_bot_client_uses_target_collection_routes() -> None:
    seen: list[tuple[str, str, dict[str, object] | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, payload))
        if request.method == "POST":
            return httpx.Response(
                202,
                json={"job": {"id": "collection-job", "type": "collection.run", "status": "queued"}},
            )
        return httpx.Response(200, json={"items": []})

    client = BotApiClient(
        base_url="http://api.test/api",
        api_token="api-token",
        transport=httpx.MockTransport(handler),
    )

    await client.start_engagement_target_collection(
        "target-1",
        window_days=30,
        requested_by="telegram:123",
    )
    await client.list_engagement_target_collection_runs("target-1")
    await client.aclose()

    assert seen == [
        (
            "POST",
            "/api/engagement/targets/target-1/collection-jobs",
            {"window_days": 30, "requested_by": "telegram:123"},
        ),
        ("GET", "/api/engagement/targets/target-1/collection-runs", None),
    ]


@pytest.mark.asyncio
async def test_bot_target_collection_commands_use_target_routes() -> None:
    client = FakeBotClient()
    collect_update = _message_update()
    runs_update = _message_update()

    await target_collect_command(collect_update, _context(client, "target-1"))
    await target_collection_runs_command(runs_update, _context(client, "target-1"))

    assert client.collection_calls == [{"target_id": "target-1", "requested_by": "telegram:123:@operator"}]
    assert client.collection_run_calls == ["target-1"]
    assert "Target engagement collection queued." in collect_update.message.replies[0]["text"]
    assert "Collection runs | latest 1" in runs_update.message.replies[0]["text"]
    assert "Messages seen: 4" in runs_update.message.replies[0]["text"]


def test_target_card_and_callbacks_expose_collection_controls() -> None:
    message = format_engagement_target_card(
        {
            "id": "target-1",
            "status": "approved",
            "allow_join": True,
            "allow_detect": True,
            "allow_post": False,
            "submitted_ref": "username:founder_circle",
        }
    )

    assert "/target_collect target-1" in message
    assert "/target_collection_runs target-1" in message
    assert parse_callback_data("eng:admin:tc:target-1") == (
        ACTION_ENGAGEMENT_TARGET_COLLECT,
        ["target-1"],
    )
    assert parse_callback_data("eng:admin:tcr:target-1") == (
        ACTION_ENGAGEMENT_TARGET_COLLECTION_RUNS,
        ["target-1"],
    )


def test_reply_opportunity_copy_keeps_legacy_candidate_id() -> None:
    message = format_engagement_candidate_card(
        {
            "id": "candidate-1",
            "community_title": "Founder Circle",
            "topic_name": "Open CRM",
            "status": "needs_review",
            "source_excerpt": "Which CRM should we try?",
            "detected_reason": "The thread is comparing CRM options.",
            "suggested_reply": "Compare data ownership first.",
        }
    )

    assert "Reply opportunity ID: candidate-1" in message
    assert "Candidate ID: candidate-1" in message


class FakeDb:
    def __init__(
        self,
        *,
        target: EngagementTarget | None = None,
        collection_runs: list[CollectionRun] | None = None,
    ) -> None:
        self.target = target
        self.collection_runs = collection_runs or []

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.target

    async def scalars(self, statement: object) -> list[object]:
        del statement
        return list(self.collection_runs)


class FakeBotClient:
    def __init__(self) -> None:
        self.collection_calls: list[dict[str, object]] = []
        self.collection_run_calls: list[str] = []

    async def start_engagement_target_collection(
        self,
        target_id: str,
        *,
        requested_by: str | None = None,
    ) -> dict[str, object]:
        self.collection_calls.append({"target_id": target_id, "requested_by": requested_by})
        return {"job": {"id": "collection-job", "type": "collection.run", "status": "queued"}}

    async def list_engagement_target_collection_runs(self, target_id: str) -> dict[str, object]:
        self.collection_run_calls.append(target_id)
        return {
            "items": [
                {
                    "id": "run-1",
                    "status": "completed",
                    "messages_seen": 4,
                    "members_seen": 2,
                    "started_at": "2026-04-22T10:00:00Z",
                    "completed_at": "2026-04-22T10:01:00Z",
                }
            ]
        }


class FakeMessage:
    def __init__(self) -> None:
        self.replies: list[dict[str, object]] = []

    async def reply_text(self, text: str, reply_markup: object | None = None) -> None:
        self.replies.append({"text": text, "reply_markup": reply_markup})


def _message_update() -> SimpleNamespace:
    user = SimpleNamespace(id=123, username="operator")
    return SimpleNamespace(message=FakeMessage(), callback_query=None, effective_user=user)


def _context(client: FakeBotClient, *args: str) -> SimpleNamespace:
    return SimpleNamespace(args=list(args), application=SimpleNamespace(bot_data={"api_client": client}))


def _target(community_id: object, *, status: str) -> EngagementTarget:
    community = Community(
        id=community_id,
        tg_id=100,
        username="founder_circle",
        title="Founder Circle",
        status=CommunityStatus.MONITORING.value,
        store_messages=False,
    )
    target = EngagementTarget(
        id=uuid4(),
        community_id=community_id,
        submitted_ref=str(community_id),
        submitted_ref_type=EngagementTargetRefType.COMMUNITY_ID.value,
        status=status,
        allow_join=True,
        allow_detect=True,
        allow_post=True,
        added_by="telegram:123",
        created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    target.community = community
    return target
