from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.deps import settings_dep
from backend.api.routes.engagement import (
    get_engagement_actions,
    get_engagement_candidates,
    get_community_engagement_settings,
    patch_engagement_topic,
    post_community_join_job,
    post_community_engagement_detect_job,
    post_engagement_candidate_approve,
    post_engagement_candidate_reject,
    post_engagement_candidate_send_job,
    post_engagement_topic,
    put_community_engagement_settings,
)
from backend.api.schemas import (
    EngagementCandidateApproveRequest,
    EngagementCandidateRejectRequest,
    EngagementDetectJobRequest,
    EngagementJoinJobRequest,
    EngagementSendJobRequest,
    EngagementSettingsUpdate,
    EngagementTopicCreate,
    EngagementTopicUpdate,
)
from backend.db.enums import (
    CommunityStatus,
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
    EngagementMode,
)
from backend.db.models import (
    Community,
    CommunityEngagementSettings,
    EngagementAction,
    EngagementCandidate,
    EngagementTopic,
)
from backend.queue.client import QueuedJob, QueueUnavailable
from backend.services.community_engagement import EngagementActionListResult, EngagementActionView


def test_engagement_routes_require_api_auth() -> None:
    app = create_app()
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace(bot_api_token="token")
    client = TestClient(app)

    response = client.get("/api/engagement/topics")

    assert response.status_code == 401


def test_join_job_route_requires_api_auth() -> None:
    app = create_app()
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace(bot_api_token="token")
    client = TestClient(app)

    response = client.post(f"/api/communities/{uuid4()}/join-jobs", json={})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_engagement_settings_returns_disabled_default() -> None:
    community_id = uuid4()
    db = FakeDb(
        community=Community(
            id=community_id,
            tg_id=100,
            status=CommunityStatus.CANDIDATE.value,
            store_messages=False,
        )
    )

    response = await get_community_engagement_settings(community_id, db)  # type: ignore[arg-type]

    assert response.mode == "disabled"
    assert response.allow_join is False
    assert response.allow_post is False
    assert response.require_approval is True
    assert response.created_at is None
    assert db.added == []


@pytest.mark.asyncio
async def test_put_engagement_settings_forces_disabled_to_read_only() -> None:
    community_id = uuid4()
    db = FakeDb(
        community=Community(
            id=community_id,
            tg_id=100,
            status=CommunityStatus.MONITORING.value,
            store_messages=False,
        )
    )

    response = await put_community_engagement_settings(
        community_id,
        EngagementSettingsUpdate(
            mode=EngagementMode.DISABLED,
            allow_join=True,
            allow_post=True,
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.mode == "disabled"
    assert response.allow_join is False
    assert response.allow_post is False
    assert response.reply_only is True
    assert db.commits == 1
    assert isinstance(db.added[0], CommunityEngagementSettings)


@pytest.mark.asyncio
async def test_put_engagement_settings_rejects_auto_limited() -> None:
    community_id = uuid4()
    db = FakeDb(
        community=Community(
            id=community_id,
            tg_id=100,
            status=CommunityStatus.MONITORING.value,
            store_messages=False,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await put_community_engagement_settings(
            community_id,
            EngagementSettingsUpdate(mode=EngagementMode.AUTO_LIMITED),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "auto_limited_not_enabled"
    assert db.commits == 0


@pytest.mark.asyncio
async def test_put_engagement_settings_requires_approved_community_for_join() -> None:
    community_id = uuid4()
    db = FakeDb(
        community=Community(
            id=community_id,
            tg_id=100,
            status=CommunityStatus.CANDIDATE.value,
            store_messages=False,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await put_community_engagement_settings(
            community_id,
            EngagementSettingsUpdate(mode=EngagementMode.SUGGEST, allow_join=True),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "community_not_engagement_approved"


@pytest.mark.asyncio
async def test_create_topic_normalizes_keywords_and_returns_guidance_fields() -> None:
    db = FakeDb()

    response = await post_engagement_topic(
        EngagementTopicCreate(
            name=" Open-source CRM ",
            description=" Helpful CRM tradeoffs ",
            stance_guidance=" Be factual and non-salesy. ",
            trigger_keywords=[" CRM ", "crm", "Open Source"],
            negative_keywords=[" Jobs "],
            example_good_replies=[" Compare support models. "],
            example_bad_replies=[" Buy now. "],
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.name == "Open-source CRM"
    assert response.description == "Helpful CRM tradeoffs"
    assert response.stance_guidance == "Be factual and non-salesy."
    assert response.trigger_keywords == ["crm", "open source"]
    assert response.negative_keywords == ["jobs"]
    assert response.example_good_replies == ["Compare support models."]
    assert response.example_bad_replies == ["Buy now."]
    assert db.commits == 1


@pytest.mark.asyncio
async def test_create_active_topic_requires_trigger_keyword() -> None:
    db = FakeDb()

    with pytest.raises(HTTPException) as exc_info:
        await post_engagement_topic(
            EngagementTopicCreate(
                name="CRM",
                stance_guidance="Be useful.",
                trigger_keywords=[],
            ),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "topic_requires_trigger_keyword"
    assert db.commits == 0


@pytest.mark.asyncio
async def test_update_topic_rejects_unsafe_guidance() -> None:
    topic_id = uuid4()
    db = FakeDb(
        topic=EngagementTopic(
            id=topic_id,
            name="CRM",
            stance_guidance="Be useful.",
            trigger_keywords=["crm"],
            negative_keywords=[],
            example_good_replies=[],
            example_bad_replies=[],
            active=True,
            created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await patch_engagement_topic(
            topic_id,
            EngagementTopicUpdate(stance_guidance="Create fake consensus."),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "unsafe_topic_guidance"


@pytest.mark.asyncio
async def test_manual_engagement_detect_job_enqueues_engagement_worker(monkeypatch) -> None:
    community_id = uuid4()
    db = FakeDb(community=_community(community_id, title="Founder Circle"))
    captured: dict[str, object] = {}

    def fake_enqueue(
        community_id_arg: object,
        *,
        window_minutes: int,
        requested_by: str,
    ) -> QueuedJob:
        captured.update(
            {
                "community_id": community_id_arg,
                "window_minutes": window_minutes,
                "requested_by": requested_by,
            }
        )
        return QueuedJob(id="detect-job", type="engagement.detect")

    monkeypatch.setattr("backend.api.routes.engagement.enqueue_manual_engagement_detect", fake_enqueue)

    response = await post_community_engagement_detect_job(
        community_id,
        EngagementDetectJobRequest(window_minutes=45, requested_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.job.id == "detect-job"
    assert response.job.type == "engagement.detect"
    assert captured == {
        "community_id": community_id,
        "window_minutes": 45,
        "requested_by": "telegram:123",
    }


@pytest.mark.asyncio
async def test_manual_engagement_detect_job_rejects_unknown_community() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await post_community_engagement_detect_job(
            uuid4(),
            EngagementDetectJobRequest(),
            FakeDb(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "not_found"


@pytest.mark.asyncio
async def test_community_join_job_enqueues_join_worker(monkeypatch) -> None:
    community_id = uuid4()
    account_id = uuid4()
    db = FakeDb(community=_community(community_id, title="Founder Circle"))
    captured: dict[str, object] = {}

    def fake_enqueue(
        community_id_arg: object,
        *,
        requested_by: str,
        telegram_account_id: object | None = None,
    ) -> QueuedJob:
        captured.update(
            {
                "community_id": community_id_arg,
                "telegram_account_id": telegram_account_id,
                "requested_by": requested_by,
            }
        )
        return QueuedJob(id="join-job", type="community.join")

    monkeypatch.setattr("backend.api.routes.engagement.enqueue_community_join", fake_enqueue)

    response = await post_community_join_job(
        community_id,
        EngagementJoinJobRequest(
            telegram_account_id=account_id,
            requested_by="telegram:123",
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.job.id == "join-job"
    assert response.job.type == "community.join"
    assert captured == {
        "community_id": community_id,
        "telegram_account_id": account_id,
        "requested_by": "telegram:123",
    }


@pytest.mark.asyncio
async def test_community_join_job_rejects_unknown_community() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await post_community_join_job(
            uuid4(),
            EngagementJoinJobRequest(),
            FakeDb(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "not_found"


@pytest.mark.asyncio
async def test_community_join_job_maps_queue_failure_to_503(monkeypatch) -> None:
    community_id = uuid4()
    db = FakeDb(community=_community(community_id, title="Founder Circle"))

    def fake_enqueue(*args: object, **kwargs: object) -> QueuedJob:
        raise QueueUnavailable("redis unavailable")

    monkeypatch.setattr("backend.api.routes.engagement.enqueue_community_join", fake_enqueue)

    with pytest.raises(HTTPException) as exc_info:
        await post_community_join_job(
            community_id,
            EngagementJoinJobRequest(),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "redis unavailable"


@pytest.mark.asyncio
async def test_list_engagement_candidates_returns_pending_review_cards() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    db = FakeDb(candidates=[candidate])

    response = await get_engagement_candidates(db, status="needs_review", limit=5, offset=0)  # type: ignore[arg-type]

    assert response.total == 1
    assert response.items[0].community_title == "Founder Circle"
    assert response.items[0].topic_name == "Open-source CRM"
    assert response.items[0].source_excerpt == "The group is comparing CRM tools."


@pytest.mark.asyncio
async def test_list_engagement_candidates_passes_community_and_topic_filters(monkeypatch) -> None:
    community_id = uuid4()
    topic_id = uuid4()
    captured: dict[str, object] = {}

    async def fake_list(db: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(items=[], limit=10, offset=5, total=0)

    monkeypatch.setattr("backend.api.routes.engagement.list_engagement_candidates", fake_list)

    response = await get_engagement_candidates(
        FakeDb(),  # type: ignore[arg-type]
        status="approved",
        community_id=community_id,
        topic_id=topic_id,
        limit=10,
        offset=5,
    )

    assert response.total == 0
    assert captured == {
        "status": "approved",
        "community_id": community_id,
        "topic_id": topic_id,
        "limit": 10,
        "offset": 5,
    }


@pytest.mark.asyncio
async def test_list_engagement_actions_returns_filtered_audit_rows() -> None:
    community_id = uuid4()
    candidate_id = uuid4()
    account_id = uuid4()
    created_at = datetime(2026, 4, 19, tzinfo=timezone.utc)
    db = FakeDb(
        actions=[
            EngagementAction(
                id=uuid4(),
                candidate_id=candidate_id,
                community_id=community_id,
                telegram_account_id=account_id,
                action_type=EngagementActionType.REPLY.value,
                status=EngagementActionStatus.SENT.value,
                outbound_text="Helpful public reply",
                reply_to_tg_message_id=123,
                sent_tg_message_id=456,
                sent_at=created_at,
                created_at=created_at,
                updated_at=created_at,
            )
        ]
    )

    response = await get_engagement_actions(
        db,  # type: ignore[arg-type]
        community_id=community_id,
        candidate_id=candidate_id,
        status="sent",
        action_type="reply",
        limit=10,
        offset=0,
    )

    assert response.total == 1
    assert response.items[0].community_id == community_id
    assert response.items[0].candidate_id == candidate_id
    assert response.items[0].telegram_account_id == account_id
    assert response.items[0].action_type == "reply"
    assert response.items[0].status == "sent"
    assert not hasattr(response.items[0], "phone")


@pytest.mark.asyncio
async def test_list_engagement_actions_passes_filters_and_pagination(monkeypatch) -> None:
    community_id = uuid4()
    candidate_id = uuid4()
    account_id = uuid4()
    action_id = uuid4()
    created_at = datetime(2026, 4, 19, tzinfo=timezone.utc)
    captured: dict[str, object] = {}

    async def fake_list(db: object, **kwargs: object) -> EngagementActionListResult:
        captured.update(kwargs)
        return EngagementActionListResult(
            items=[
                EngagementActionView(
                    id=action_id,
                    candidate_id=candidate_id,
                    community_id=community_id,
                    telegram_account_id=account_id,
                    action_type="join",
                    status="failed",
                    outbound_text=None,
                    reply_to_tg_message_id=None,
                    sent_tg_message_id=None,
                    scheduled_at=None,
                    sent_at=None,
                    error_message="inaccessible",
                    created_at=created_at,
                )
            ],
            limit=7,
            offset=14,
            total=21,
        )

    monkeypatch.setattr("backend.api.routes.engagement.list_engagement_actions", fake_list)

    response = await get_engagement_actions(
        FakeDb(),  # type: ignore[arg-type]
        community_id=community_id,
        candidate_id=candidate_id,
        status="failed",
        action_type="join",
        limit=7,
        offset=14,
    )

    assert response.total == 21
    assert response.items[0].id == action_id
    assert captured == {
        "community_id": community_id,
        "candidate_id": candidate_id,
        "status": "failed",
        "action_type": "join",
        "limit": 7,
        "offset": 14,
    }


@pytest.mark.asyncio
async def test_approve_engagement_candidate_records_review_metadata() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    db = FakeDb(scalar_result=candidate)

    response = await post_engagement_candidate_approve(
        candidate.id,
        EngagementCandidateApproveRequest(reviewed_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.status == EngagementCandidateStatus.APPROVED.value
    assert response.reviewed_by == "telegram:123"
    assert response.reviewed_at is not None
    assert response.final_reply == candidate.suggested_reply
    assert db.commits == 1


@pytest.mark.asyncio
async def test_approve_engagement_candidate_rejects_expired_candidate() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(
        uuid4(),
        community,
        topic,
        expires_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
    )
    db = FakeDb(scalar_result=candidate)

    with pytest.raises(HTTPException) as exc_info:
        await post_engagement_candidate_approve(
            candidate.id,
            EngagementCandidateApproveRequest(reviewed_by="telegram:123"),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "candidate_expired"
    assert db.commits == 0


@pytest.mark.asyncio
async def test_reject_engagement_candidate_records_review_metadata() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    db = FakeDb(scalar_result=candidate)

    response = await post_engagement_candidate_reject(
        candidate.id,
        EngagementCandidateRejectRequest(reviewed_by="telegram:123", reason="Not useful"),
        db,  # type: ignore[arg-type]
    )

    assert response.status == EngagementCandidateStatus.REJECTED.value
    assert response.reviewed_by == "telegram:123"
    assert response.reviewed_at is not None
    assert db.commits == 1


@pytest.mark.asyncio
async def test_engagement_send_job_enqueues_for_approved_candidate(monkeypatch) -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    candidate.status = EngagementCandidateStatus.APPROVED.value
    candidate.reviewed_by = "telegram:123"
    db = FakeDb(candidate=candidate)
    captured: dict[str, object] = {}

    def fake_enqueue(candidate_id_arg: object, *, approved_by: str) -> QueuedJob:
        captured.update({"candidate_id": candidate_id_arg, "approved_by": approved_by})
        return QueuedJob(id="send-job", type="engagement.send")

    monkeypatch.setattr("backend.api.routes.engagement.enqueue_engagement_send", fake_enqueue)

    response = await post_engagement_candidate_send_job(
        candidate.id,
        EngagementSendJobRequest(),
        db,  # type: ignore[arg-type]
    )

    assert response.job.id == "send-job"
    assert response.job.type == "engagement.send"
    assert captured == {"candidate_id": candidate.id, "approved_by": "telegram:123"}


@pytest.mark.asyncio
async def test_engagement_send_job_rejects_unapproved_candidate() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    db = FakeDb(candidate=candidate)

    with pytest.raises(HTTPException) as exc_info:
        await post_engagement_candidate_send_job(
            candidate.id,
            EngagementSendJobRequest(approved_by="telegram:123"),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "candidate_not_approved"


class FakeDb:
    def __init__(
        self,
        *,
        community: Community | None = None,
        settings: CommunityEngagementSettings | None = None,
        topic: EngagementTopic | None = None,
        candidate: EngagementCandidate | None = None,
        candidates: list[EngagementCandidate] | None = None,
        actions: list[EngagementAction] | None = None,
        scalar_result: object | None = None,
    ) -> None:
        self.community = community
        self.settings = settings
        self.topic = topic
        self.candidate = candidate
        self.candidates = candidates
        self.actions = actions
        self.scalar_result = scalar_result
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0

    async def get(self, model: object, item_id: object) -> object | None:
        if model is Community:
            return self.community
        if model is EngagementTopic:
            return self.topic
        if model is EngagementCandidate:
            return self.candidate
        return None

    async def scalar(self, statement: object) -> object | None:
        if self.scalar_result is not None:
            return self.scalar_result
        if self.candidates is not None:
            return len(self.candidates)
        if self.actions is not None:
            return len(self.actions)
        return self.settings

    async def scalars(self, statement: object) -> list[object]:
        del statement
        if self.actions is not None:
            return list(self.actions)
        return list(self.candidates or [])

    def add(self, model: object) -> None:
        self.added.append(model)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1


def _community(community_id: object, *, title: str) -> Community:
    return Community(
        id=community_id,
        tg_id=100,
        username="founder_circle",
        title=title,
        status=CommunityStatus.MONITORING.value,
        store_messages=False,
    )


def _topic(topic_id: object, *, name: str) -> EngagementTopic:
    return EngagementTopic(
        id=topic_id,
        name=name,
        stance_guidance="Be useful.",
        trigger_keywords=["crm"],
        negative_keywords=[],
        example_good_replies=[],
        example_bad_replies=[],
        active=True,
        created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
    )


def _candidate(
    candidate_id: object,
    community: Community,
    topic: EngagementTopic,
    *,
    expires_at: datetime | None = None,
) -> EngagementCandidate:
    candidate = EngagementCandidate(
        id=candidate_id,
        community_id=community.id,
        topic_id=topic.id,
        source_tg_message_id=123,
        source_excerpt="The group is comparing CRM tools.",
        detected_reason="The group is comparing CRM alternatives.",
        suggested_reply="Compare data ownership, integrations, and exit paths first.",
        risk_notes=[],
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        expires_at=expires_at or datetime(2999, 4, 20, tzinfo=timezone.utc),
        created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
    )
    candidate.community = community
    candidate.topic = topic
    return candidate
