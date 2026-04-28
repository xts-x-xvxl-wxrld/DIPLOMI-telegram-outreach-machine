from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.deps import settings_dep
from backend.api.routes.engagement import (
    patch_engagement,
    get_engagement_style_rule_detail,
    get_engagement_target_detail,
    get_engagement_topic_detail,
    get_community_engagement_settings,
    patch_engagement_style_rule,
    patch_engagement_topic,
    post_community_join_job,
    post_community_engagement_detect_job,
    post_engagement_style_rule,
    post_engagement_target,
    post_engagement_target_detect_job,
    post_engagement_target_join_job,
    post_engagement_target_resolve_job,
    patch_engagement_target,
    post_engagement_topic,
    post_task_first_engagement,
    post_task_first_wizard_confirm,
    post_task_first_wizard_retry,
    put_community_engagement_settings,
    put_task_first_settings,
)
from backend.api.schemas import (
    EngagementDetectJobRequest,
    EngagementJoinJobRequest,
    EngagementSettingsUpdate,
    EngagementStyleRuleCreateRequest,
    EngagementStyleRuleUpdateRequest,
    EngagementTargetCreateRequest,
    EngagementTargetResolveJobRequest,
    EngagementTargetUpdateRequest,
    EngagementTopicCreate,
    EngagementTopicUpdate,
    TaskFirstEngagementCreateRequest,
    TaskFirstEngagementPatchRequest,
    TaskFirstEngagementSettingsUpdate,
    TaskFirstWizardActionRequest,
)
from backend.db.enums import (
    AccountPool,
    AccountStatus,
    CommunityAccountMembershipStatus,
    CommunityStatus,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementStatus,
    EngagementTargetRefType,
    EngagementTargetStatus,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
    Engagement,
    EngagementAction,
    EngagementCandidate,
    EngagementCandidateRevision,
    EngagementSettings,
    EngagementTarget,
    EngagementTopic,
    EngagementStyleRule,
    TelegramAccount,
)
from backend.queue.client import QueuedJob, QueueUnavailable

_FIXTURE_NOW = datetime.now(timezone.utc).replace(microsecond=0)


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


def test_operator_capabilities_use_backend_admin_allowlist() -> None:
    app = create_app()
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace(
        bot_api_token="token",
        engagement_admin_user_ids="123, 999",
    )
    client = TestClient(app)

    admin_response = client.get(
        "/api/operator/capabilities",
        headers={"Authorization": "Bearer token", "X-Telegram-User-Id": "123"},
    )
    non_admin_response = client.get(
        "/api/operator/capabilities",
        headers={"Authorization": "Bearer token", "X-Telegram-User-Id": "456"},
    )

    assert admin_response.status_code == 200
    assert admin_response.json()["backend_capabilities_available"] is True
    assert admin_response.json()["engagement_admin"] is True
    assert non_admin_response.status_code == 200
    assert non_admin_response.json()["engagement_admin"] is False


def test_operator_capabilities_report_unconfigured_backend_for_rollout_fallback() -> None:
    app = create_app()
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace(
        bot_api_token="token",
        engagement_admin_user_ids="",
    )
    client = TestClient(app)

    response = client.get(
        "/api/operator/capabilities",
        headers={"Authorization": "Bearer token", "X-Telegram-User-Id": "123"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "operator_user_id": 123,
        "backend_capabilities_available": False,
        "engagement_admin": None,
        "source": "unconfigured",
    }


def test_admin_mutation_route_rejects_non_admin_when_backend_capabilities_are_configured() -> None:
    app = create_app()
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace(
        bot_api_token="token",
        engagement_admin_user_ids="123",
    )
    client = TestClient(app)

    response = client.post(
        "/api/engagement/topics",
        headers={"Authorization": "Bearer token", "X-Telegram-User-Id": "456"},
        json={
            "name": "CRM",
            "stance_guidance": "Be concise.",
            "trigger_keywords": ["crm"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "engagement_admin_required"

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
async def test_put_engagement_settings_accepts_auto_limited() -> None:
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
        EngagementSettingsUpdate(mode=EngagementMode.AUTO_LIMITED),
        db,  # type: ignore[arg-type]
    )

    assert response.mode == EngagementMode.AUTO_LIMITED.value
    assert db.commits == 1

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
async def test_put_engagement_settings_rejects_assigned_search_account() -> None:
    community_id = uuid4()
    account_id = uuid4()
    db = FakeDb(
        community=Community(
            id=community_id,
            tg_id=100,
            status=CommunityStatus.MONITORING.value,
            store_messages=False,
        ),
        account=TelegramAccount(
            id=account_id,
            phone="+123456789",
            session_file_path="search.session",
            account_pool=AccountPool.SEARCH.value,
            status=AccountStatus.AVAILABLE.value,
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await put_community_engagement_settings(
            community_id,
            EngagementSettingsUpdate(assigned_account_id=account_id),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "assigned_account_wrong_pool"
    assert db.commits == 0

@pytest.mark.asyncio
async def test_put_engagement_settings_accepts_assigned_engagement_account() -> None:
    community_id = uuid4()
    account_id = uuid4()
    db = FakeDb(
        community=Community(
            id=community_id,
            tg_id=100,
            status=CommunityStatus.MONITORING.value,
            store_messages=False,
        ),
        account=TelegramAccount(
            id=account_id,
            phone="+123456789",
            session_file_path="engagement.session",
            account_pool=AccountPool.ENGAGEMENT.value,
            status=AccountStatus.AVAILABLE.value,
        ),
    )

    response = await put_community_engagement_settings(
        community_id,
        EngagementSettingsUpdate(assigned_account_id=account_id),
        db,  # type: ignore[arg-type]
    )

    assert response.assigned_account_id == account_id
    assert db.commits == 1

@pytest.mark.asyncio
async def test_post_task_first_engagement_creates_draft_for_resolved_target() -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.RESOLVED.value)
    db = FakeDb(target=target)

    response = await post_task_first_engagement(
        TaskFirstEngagementCreateRequest(target_id=target.id, created_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.result == "created"
    assert response.engagement.target_id == target.id
    assert response.engagement.community_id == community_id
    assert response.engagement.status == EngagementStatus.DRAFT.value
    assert isinstance(db.added[0], Engagement)
    assert db.commits == 1

@pytest.mark.asyncio
async def test_post_task_first_engagement_reuses_existing_row() -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, status=EngagementStatus.ACTIVE.value)
    db = FakeDb(target=target, engagement=engagement)

    response = await post_task_first_engagement(
        TaskFirstEngagementCreateRequest(target_id=target.id, created_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.result == "existing"
    assert response.engagement.id == engagement.id
    assert db.added == []
    assert db.commits == 1

@pytest.mark.asyncio
async def test_patch_task_first_engagement_updates_topic_and_name() -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.RESOLVED.value)
    engagement = _engagement(target=target)
    topic = _topic(uuid4(), name="CRM")
    db = FakeDb(target=target, engagement=engagement, topic=topic)

    response = await patch_engagement(
        engagement.id,
        TaskFirstEngagementPatchRequest(topic_id=topic.id, name="Founder CRM"),
        db,  # type: ignore[arg-type]
    )

    assert response.result == "updated"
    assert response.engagement is not None
    assert response.engagement.topic_id == topic.id
    assert response.engagement.name == "Founder CRM"
    assert db.commits == 1

@pytest.mark.asyncio
async def test_put_task_first_settings_accepts_auto_send_and_account() -> None:
    community_id = uuid4()
    account_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.RESOLVED.value)
    engagement = _engagement(target=target)
    db = FakeDb(
        target=target,
        engagement=engagement,
        account=TelegramAccount(
            id=account_id,
            phone="+123456789",
            session_file_path="engagement.session",
            account_pool=AccountPool.ENGAGEMENT.value,
            status=AccountStatus.AVAILABLE.value,
        ),
    )

    response = await put_task_first_settings(
        engagement.id,
        TaskFirstEngagementSettingsUpdate(
            assigned_account_id=account_id,
            mode=EngagementMode.AUTO_LIMITED,
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.result == "updated"
    assert response.settings is not None
    assert response.settings.assigned_account_id == account_id
    assert response.settings.mode == EngagementMode.AUTO_LIMITED.value
    created_settings = next(item for item in db.added if isinstance(item, EngagementSettings))
    assert created_settings.allow_join is True
    assert created_settings.allow_post is True
    assert db.commits == 1

@pytest.mark.asyncio
async def test_put_task_first_settings_blocks_invalid_account() -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.RESOLVED.value)
    engagement = _engagement(target=target)
    db = FakeDb(target=target, engagement=engagement)

    response = await put_task_first_settings(
        engagement.id,
        TaskFirstEngagementSettingsUpdate(assigned_account_id=uuid4()),
        db,  # type: ignore[arg-type]
    )

    assert response.result == "blocked"
    assert response.code == "account_missing"
    assert db.commits == 0

@pytest.mark.asyncio
async def test_task_first_wizard_confirm_requires_topic() -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.RESOLVED.value)
    engagement = _engagement(target=target)
    db = FakeDb(target=target, engagement=engagement)

    response = await post_task_first_wizard_confirm(
        engagement.id,
        TaskFirstWizardActionRequest(requested_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.result == "validation_failed"
    assert response.field == "topic"
    assert db.commits == 0

@pytest.mark.asyncio
async def test_task_first_wizard_confirm_blocks_unjoined_account() -> None:
    community_id = uuid4()
    account_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.RESOLVED.value)
    topic = _topic(uuid4(), name="CRM")
    engagement = _engagement(target=target, topic=topic)
    settings = _engagement_settings(engagement.id, account_id=account_id, mode=EngagementMode.SUGGEST.value)
    db = FakeDb(target=target, engagement=engagement, topic=topic, engagement_settings=settings)

    response = await post_task_first_wizard_confirm(
        engagement.id,
        TaskFirstWizardActionRequest(requested_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.result == "blocked"
    assert response.code == "account_not_joined"
    assert db.commits == 0

@pytest.mark.asyncio
async def test_task_first_wizard_confirm_approves_target_and_activates_engagement(monkeypatch) -> None:
    community_id = uuid4()
    account_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.RESOLVED.value)
    topic = _topic(uuid4(), name="CRM")
    engagement = _engagement(target=target, topic=topic)
    settings = _engagement_settings(engagement.id, account_id=account_id, mode=EngagementMode.AUTO_LIMITED.value)
    membership = _membership(community_id=community_id, account_id=account_id)
    db = FakeDb(
        target=target,
        engagement=engagement,
        topic=topic,
        engagement_settings=settings,
        membership=membership,
    )
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

    response = await post_task_first_wizard_confirm(
        engagement.id,
        TaskFirstWizardActionRequest(requested_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.result == "confirmed"
    assert response.engagement_status == EngagementStatus.ACTIVE.value
    assert response.target_status == EngagementTargetStatus.APPROVED.value
    assert target.allow_join is True
    assert target.allow_detect is True
    assert target.allow_post is True
    assert captured == {
        "community_id": community_id,
        "window_minutes": 60,
        "requested_by": "telegram:123",
    }
    assert db.commits == 1

@pytest.mark.asyncio
async def test_task_first_wizard_retry_clears_draft_state() -> None:
    community_id = uuid4()
    account_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.RESOLVED.value)
    topic = _topic(uuid4(), name="CRM")
    engagement = _engagement(target=target, topic=topic)
    settings = _engagement_settings(engagement.id, account_id=account_id, mode=EngagementMode.SUGGEST.value)
    db = FakeDb(target=target, engagement=engagement, topic=topic, engagement_settings=settings)

    response = await post_task_first_wizard_retry(
        engagement.id,
        db,  # type: ignore[arg-type]
    )

    assert response.result == "reset"
    assert engagement.topic_id is None
    assert settings.assigned_account_id is None
    assert settings.mode == EngagementMode.DISABLED.value
    assert db.commits == 1

@pytest.mark.asyncio
async def test_create_engagement_target_from_existing_community() -> None:
    community_id = uuid4()
    db = FakeDb(community=_community(community_id, title="Founder Circle"))

    response = await post_engagement_target(
        EngagementTargetCreateRequest(
            target_ref=str(community_id),
            added_by="telegram:123",
            notes="Manual engagement target",
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.community_id == community_id
    assert response.status == EngagementTargetStatus.RESOLVED.value
    assert response.submitted_ref_type == EngagementTargetRefType.COMMUNITY_ID.value
    assert response.allow_join is False
    assert response.allow_detect is False
    assert response.allow_post is False
    assert response.notes == "Manual engagement target"
    assert db.commits == 1
    assert isinstance(db.added[0], EngagementTarget)

@pytest.mark.asyncio
async def test_create_engagement_target_from_public_username_is_pending() -> None:
    db = FakeDb()

    response = await post_engagement_target(
        EngagementTargetCreateRequest(target_ref="@Example_Channel", added_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.community_id is None
    assert response.status == EngagementTargetStatus.PENDING.value
    assert response.submitted_ref == "username:example_channel"
    assert response.submitted_ref_type == EngagementTargetRefType.TELEGRAM_USERNAME.value
    assert db.commits == 1

@pytest.mark.asyncio
async def test_duplicate_engagement_target_returns_existing_row() -> None:
    target = _target(uuid4(), status=EngagementTargetStatus.PENDING.value)
    target.community_id = None
    target.submitted_ref = "username:example"
    target.submitted_ref_type = EngagementTargetRefType.TELEGRAM_USERNAME.value
    db = FakeDb(target=target)

    response = await post_engagement_target(
        EngagementTargetCreateRequest(target_ref="@example", added_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.id == target.id
    assert db.added == []
    assert db.commits == 1

@pytest.mark.asyncio
async def test_get_engagement_target_detail_returns_target_card_fields() -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    db = FakeDb(target=target)

    response = await get_engagement_target_detail(target.id, db)  # type: ignore[arg-type]

    assert response.id == target.id
    assert response.community_id == community_id
    assert response.community_title == "Founder Circle"
    assert response.status == EngagementTargetStatus.APPROVED.value
    assert response.allow_detect is True

@pytest.mark.asyncio
async def test_patch_engagement_target_approves_permissions() -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.RESOLVED.value)
    target.allow_join = False
    target.allow_detect = False
    target.allow_post = False
    db = FakeDb(target=target)

    response = await patch_engagement_target(
        target.id,
        EngagementTargetUpdateRequest(
            status=EngagementTargetStatus.APPROVED,
            allow_join=True,
            allow_detect=True,
            allow_post=True,
            updated_by="telegram:123",
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.status == EngagementTargetStatus.APPROVED.value
    assert response.allow_join is True
    assert response.allow_detect is True
    assert response.allow_post is True
    assert response.approved_by == "telegram:123"
    assert response.approved_at is not None
    assert db.commits == 1

@pytest.mark.asyncio
async def test_engagement_target_resolve_job_enqueues_engagement_job(monkeypatch) -> None:
    target = _target(uuid4(), status=EngagementTargetStatus.PENDING.value)
    db = FakeDb(target=target)
    captured: dict[str, object] = {}

    def fake_enqueue(target_id_arg: object, *, requested_by: str) -> QueuedJob:
        captured.update({"target_id": target_id_arg, "requested_by": requested_by})
        return QueuedJob(id="target-resolve-job", type="engagement_target.resolve")

    monkeypatch.setattr("backend.api.routes.engagement.enqueue_engagement_target_resolve", fake_enqueue)

    response = await post_engagement_target_resolve_job(
        target.id,
        EngagementTargetResolveJobRequest(requested_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.job.id == "target-resolve-job"
    assert response.job.type == "engagement_target.resolve"
    assert captured == {"target_id": target.id, "requested_by": "telegram:123"}

@pytest.mark.asyncio
async def test_engagement_target_join_job_uses_resolved_target_community(monkeypatch) -> None:
    community_id = uuid4()
    account_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    db = FakeDb(target=target)
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
        return QueuedJob(id="target-join-job", type="community.join")

    monkeypatch.setattr("backend.api.routes.engagement.enqueue_community_join", fake_enqueue)

    response = await post_engagement_target_join_job(
        target.id,
        EngagementJoinJobRequest(
            telegram_account_id=account_id,
            requested_by="telegram:123",
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.job.id == "target-join-job"
    assert response.job.type == "community.join"
    assert captured == {
        "community_id": community_id,
        "telegram_account_id": account_id,
        "requested_by": "telegram:123",
    }

@pytest.mark.asyncio
async def test_engagement_target_detect_job_uses_resolved_target_community(monkeypatch) -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    db = FakeDb(target=target)
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
        return QueuedJob(id="target-detect-job", type="engagement.detect")

    monkeypatch.setattr("backend.api.routes.engagement.enqueue_manual_engagement_detect", fake_enqueue)

    response = await post_engagement_target_detect_job(
        target.id,
        EngagementDetectJobRequest(window_minutes=45, requested_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.job.id == "target-detect-job"
    assert response.job.type == "engagement.detect"
    assert captured == {
        "community_id": community_id,
        "window_minutes": 45,
        "requested_by": "telegram:123",
    }

@pytest.mark.asyncio
async def test_engagement_target_jobs_reject_unresolved_target() -> None:
    target = _target(uuid4(), status=EngagementTargetStatus.PENDING.value)
    target.community_id = None
    db = FakeDb(target=target)

    with pytest.raises(HTTPException) as exc_info:
        await post_engagement_target_join_job(
            target.id,
            EngagementJoinJobRequest(),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "target_not_resolved"

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
async def test_create_active_topic_allows_semantic_profile_without_trigger_keyword() -> None:
    db = FakeDb()

    response = await post_engagement_topic(
        EngagementTopicCreate(
            name="CRM",
            description="People comparing CRM migration and evaluation tradeoffs.",
            stance_guidance="Be useful.",
            trigger_keywords=[],
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.description == "People comparing CRM migration and evaluation tradeoffs."
    assert response.trigger_keywords == []
    assert db.commits == 1

@pytest.mark.asyncio
async def test_create_active_topic_requires_semantic_profile_text() -> None:
    db = FakeDb()

    with pytest.raises(HTTPException) as exc_info:
        await post_engagement_topic(
            EngagementTopicCreate(
                name="CRM",
                stance_guidance="Be useful.",
                trigger_keywords=[],
                description=None,
                example_good_replies=[],
            ),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "topic_requires_semantic_profile"
    assert db.commits == 0

@pytest.mark.asyncio
async def test_get_engagement_topic_detail_returns_topic() -> None:
    topic_id = uuid4()
    db = FakeDb(topic=_topic(topic_id, name="CRM"))

    response = await get_engagement_topic_detail(topic_id, db)  # type: ignore[arg-type]

    assert response.id == topic_id
    assert response.name == "CRM"

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
async def test_style_rule_routes_create_update_and_detail() -> None:
    rule_id = uuid4()
    db = FakeDb(
        style_rule=EngagementStyleRule(
            id=rule_id,
            scope_type="global",
            scope_id=None,
            name="Keep it brief",
            rule_text="Keep replies under three sentences.",
            active=True,
            priority=50,
            created_by="operator",
            updated_by="operator",
            created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
        )
    )

    created = await post_engagement_style_rule(
        EngagementStyleRuleCreateRequest(
            scope_type="global",
            scope_id=None,
            name="Mention tradeoffs",
            priority=75,
            rule_text="Mention tradeoffs before recommendations.",
            created_by="telegram:123",
        ),
        FakeDb(),  # type: ignore[arg-type]
    )
    detail = await get_engagement_style_rule_detail(rule_id, db)  # type: ignore[arg-type]
    updated = await patch_engagement_style_rule(
        rule_id,
        EngagementStyleRuleUpdateRequest(active=False, updated_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert created.name == "Mention tradeoffs"
    assert created.priority == 75
    assert detail.id == rule_id
    assert updated.active is False

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
class FakeDb:
    def __init__(
        self,
        *,
        community: Community | None = None,
        settings: CommunityEngagementSettings | None = None,
        engagement: Engagement | None = None,
        engagement_settings: EngagementSettings | None = None,
        membership: CommunityAccountMembership | None = None,
        topic: EngagementTopic | None = None,
        style_rule: EngagementStyleRule | None = None,
        target: EngagementTarget | None = None,
        candidate: EngagementCandidate | None = None,
        candidates: list[EngagementCandidate] | None = None,
        revisions: list[EngagementCandidateRevision] | None = None,
        actions: list[EngagementAction] | None = None,
        account: TelegramAccount | None = None,
        scalar_result: object | None = None,
    ) -> None:
        self.community = community
        self.settings = settings
        self.engagement = engagement
        self.engagement_settings = engagement_settings
        self.membership = membership
        self.topic = topic
        self.style_rule = style_rule
        self.target = target
        self.candidate = candidate
        self.candidates = candidates
        self.revisions = revisions
        self.actions = actions
        self.account = account
        self.scalar_result = scalar_result
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0

    async def get(self, model: object, item_id: object) -> object | None:
        if model is Community:
            return self.community
        if model is Engagement:
            return self.engagement
        if model is EngagementSettings:
            return self.engagement_settings
        if model is CommunityAccountMembership:
            return self.membership
        if model is EngagementTopic:
            return self.topic
        if model is EngagementStyleRule:
            return self.style_rule
        if model is EngagementTarget:
            return self.target
        if model is EngagementCandidate:
            return self.candidate
        if model is TelegramAccount:
            return self.account
        return None

    async def scalar(self, statement: object) -> object | None:
        if self.scalar_result is not None:
            return self.scalar_result
        model_name = _selected_model_name(statement)
        if model_name == "Engagement":
            return self.engagement
        if model_name == "EngagementSettings":
            return self.engagement_settings
        if model_name == "CommunityAccountMembership":
            return self.membership
        if self.target is not None:
            return self.target
        if self.candidates is not None:
            return len(self.candidates)
        if self.actions is not None:
            return len(self.actions)
        return self.settings

    async def scalars(self, statement: object) -> list[object]:
        del statement
        if self.revisions is not None:
            return list(self.revisions)
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
        created_at=_now(),
        updated_at=_now(),
    )


def _engagement(
    *,
    target: EngagementTarget,
    topic: EngagementTopic | None = None,
    status: str = EngagementStatus.DRAFT.value,
) -> Engagement:
    return Engagement(
        id=uuid4(),
        target_id=target.id,
        community_id=target.community_id,
        topic_id=None if topic is None else topic.id,
        status=status,
        name=None,
        created_by="telegram:123",
        created_at=_now(),
        updated_at=_now(),
    )


def _engagement_settings(
    engagement_id: object,
    *,
    account_id: object | None,
    mode: str,
) -> EngagementSettings:
    allow_post = mode == EngagementMode.AUTO_LIMITED.value
    return EngagementSettings(
        id=uuid4(),
        engagement_id=engagement_id,
        mode=mode,
        allow_join=mode in {EngagementMode.SUGGEST.value, EngagementMode.AUTO_LIMITED.value},
        allow_post=allow_post,
        reply_only=True,
        require_approval=True,
        max_posts_per_day=1,
        min_minutes_between_posts=240,
        quiet_hours_start=None,
        quiet_hours_end=None,
        assigned_account_id=account_id,
        created_at=_now(),
        updated_at=_now(),
    )


def _membership(*, community_id: object, account_id: object) -> CommunityAccountMembership:
    return CommunityAccountMembership(
        id=uuid4(),
        community_id=community_id,
        telegram_account_id=account_id,
        status=CommunityAccountMembershipStatus.JOINED.value,
        joined_at=_now(),
        last_checked_at=_now(),
        last_error=None,
        created_at=_now(),
        updated_at=_now(),
    )


def _selected_model_name(statement: object) -> str | None:
    descriptions = getattr(statement, "column_descriptions", None)
    if not descriptions:
        return None
    entity = descriptions[0].get("entity")
    return None if entity is None else getattr(entity, "__name__", None)


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
        source_message_date=_now() - timedelta(minutes=30),
        detected_at=_now() - timedelta(minutes=25),
        detected_reason="The group is comparing CRM alternatives.",
        moment_strength="good",
        timeliness="fresh",
        reply_value="practical_tip",
        suggested_reply="Compare data ownership, integrations, and exit paths first.",
        risk_notes=[],
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        review_deadline_at=_now() + timedelta(minutes=30),
        reply_deadline_at=_now() + timedelta(minutes=60),
        expires_at=expires_at or datetime(2999, 4, 20, tzinfo=timezone.utc),
        created_at=_now(),
        updated_at=_now(),
    )
    candidate.community = community
    candidate.topic = topic
    return candidate


def _target(
    community_id: object,
    *,
    status: str = EngagementTargetStatus.APPROVED.value,
) -> EngagementTarget:
    community = _community(community_id, title="Founder Circle")
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
        created_at=_now(),
        updated_at=_now(),
    )
    target.community = community
    return target


def _now() -> datetime:
    return _FIXTURE_NOW
