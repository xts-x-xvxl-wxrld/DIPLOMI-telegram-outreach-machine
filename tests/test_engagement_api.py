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
    get_engagement_cockpit_issue_rate_limit,
    get_engagement_cockpit_quiet_hours,
    get_engagement_cockpit_approvals,
    get_engagement_cockpit_engagement_detail,
    get_engagement_cockpit_engagements,
    get_engagement_cockpit_home,
    get_engagement_cockpit_issues,
    get_engagement_cockpit_scoped_approvals,
    get_engagement_cockpit_scoped_issues,
    get_engagement_cockpit_sent,
    get_engagement_style_rule_detail,
    get_engagement_target_detail,
    get_engagement_topic_detail,
    get_community_engagement_settings,
    patch_engagement_style_rule,
    patch_engagement_topic,
    post_engagement_cockpit_draft_approve,
    post_engagement_cockpit_draft_edit,
    post_engagement_cockpit_draft_reject,
    post_engagement_cockpit_issue_action,
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
    post_task_first_wizard_retry,
    put_community_engagement_settings,
    put_engagement_cockpit_quiet_hours,
    put_task_first_settings,
)
from backend.api.schemas import (
    CockpitDraftEditRequest,
    CockpitQuietHoursWriteRequest,
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
    EngagementDraftUpdateRequest,
    EngagementSettings,
    EngagementTarget,
    EngagementTopic,
    EngagementStyleRule,
    TelegramAccount,
)
from backend.queue.client import QueuedJob, QueueUnavailable
from backend.services.task_first_engagement_draft_updates import complete_draft_update_request

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
async def test_get_engagement_settings_prefers_active_task_first_settings() -> None:
    community_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, status=EngagementStatus.ACTIVE.value)
    account_id = uuid4()
    db = FakeDb(
        community=target.community,
        target=target,
        engagement=engagement,
        engagement_settings=_engagement_settings(
            engagement.id,
            account_id=account_id,
            mode=EngagementMode.SUGGEST.value,
        ),
    )

    response = await get_community_engagement_settings(community_id, db)  # type: ignore[arg-type]

    assert response.mode == EngagementMode.SUGGEST.value
    assert response.assigned_account_id == account_id

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
async def test_cockpit_home_selects_first_run_approvals_issues_and_clear_states() -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    active = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    settings = _engagement_settings(active.id, account_id=uuid4(), mode=EngagementMode.SUGGEST.value)

    first_run = await get_engagement_cockpit_home(
        FakeDb(targets=[target], topics=[topic], engagements=[_engagement(target=target)]),  # type: ignore[arg-type]
    )
    assert first_run.state == "first_run"
    assert first_run.active_engagement_count == 0

    approvals = await get_engagement_cockpit_home(
        FakeDb(
            targets=[target],
            topics=[topic],
            engagements=[active],
            engagement_settings_rows=[settings],
            candidates=[_candidate(uuid4(), target.community, topic)],
        ),  # type: ignore[arg-type]
    )
    assert approvals.state == "approvals"
    assert approvals.draft_count == 1
    assert approvals.next_draft_preview is not None

    issues = await get_engagement_cockpit_home(
        FakeDb(
            targets=[target],
            engagements=[_engagement(target=target, status=EngagementStatus.ACTIVE.value)],
            engagement_settings_rows=[settings],
        ),  # type: ignore[arg-type]
    )
    assert issues.state == "issues"
    assert issues.issue_count == 2
    assert issues.latest_issue_preview is not None
    assert issues.latest_issue_preview.issue_label == "Topics not chosen"

    clear = await get_engagement_cockpit_home(
        FakeDb(
            targets=[target],
            topics=[topic],
            engagements=[active],
            engagement_settings_rows=[settings],
            memberships=[_membership(community_id=community_id, account_id=settings.assigned_account_id)],
            actions=[_action(uuid4(), community=target.community, sent_at=_now())],
        ),  # type: ignore[arg-type]
    )
    assert clear.state == "clear"
    assert clear.has_sent_messages is True

@pytest.mark.asyncio
async def test_cockpit_approvals_global_and_scoped_share_queue_shape() -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    active = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    candidate = _candidate(uuid4(), target.community, topic)
    db = FakeDb(targets=[target], topics=[topic], engagements=[active], candidates=[candidate])

    global_queue = await get_engagement_cockpit_approvals(db)  # type: ignore[arg-type]
    scoped_queue = await get_engagement_cockpit_scoped_approvals(active.id, db)  # type: ignore[arg-type]

    assert global_queue.empty_state == "none"
    assert global_queue.queue_count == 1
    assert global_queue.placeholders == []
    assert global_queue.current is not None
    assert global_queue.current.draft_id == candidate.id
    assert scoped_queue.model_dump() == global_queue.model_dump()

@pytest.mark.asyncio
async def test_cockpit_approvals_do_not_invent_placeholders_without_update_state() -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    active = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    candidate = _candidate(
        uuid4(),
        target.community,
        topic,
        final_reply="Make it shorter.",
        operator_notified_at=_now() - timedelta(minutes=10),
        reviewed_at=_now() - timedelta(minutes=5),
    )
    db = FakeDb(targets=[target], topics=[topic], engagements=[active], candidates=[candidate])

    queue = await get_engagement_cockpit_approvals(db)  # type: ignore[arg-type]

    assert queue.queue_count == 1
    assert queue.updating_count == 0
    assert queue.empty_state == "none"
    assert queue.placeholders == []
    assert queue.current is not None
    assert queue.current.draft_id == candidate.id

@pytest.mark.asyncio
async def test_cockpit_approvals_surface_pending_placeholders_and_updated_draft_badges() -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    pending_candidate = _candidate(
        uuid4(),
        target.community,
        topic,
        created_at=_now(),
        updated_at=_now(),
    )
    replacement_candidate = _candidate(
        uuid4(),
        target.community,
        topic,
        created_at=_now() - timedelta(minutes=20),
        updated_at=_now() - timedelta(minutes=20),
    )
    db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        candidates=[pending_candidate, replacement_candidate],
        draft_update_requests=[
            _draft_update_request(
                engagement_id=engagement.id,
                source_candidate_id=pending_candidate.id,
                status="pending",
                source_queue_created_at=pending_candidate.created_at,
            ),
            _draft_update_request(
                engagement_id=engagement.id,
                source_candidate_id=uuid4(),
                replacement_candidate_id=replacement_candidate.id,
                status="completed",
                source_queue_created_at=replacement_candidate.created_at - timedelta(minutes=5),
            ),
        ],
    )

    queue = await get_engagement_cockpit_approvals(db)  # type: ignore[arg-type]

    assert queue.queue_count == 1
    assert queue.updating_count == 1
    assert queue.empty_state == "none"
    assert queue.placeholders[0].label == "Updating draft"
    assert queue.current is not None
    assert queue.current.draft_id == replacement_candidate.id
    assert queue.current.badge == "Updated draft"


@pytest.mark.asyncio
async def test_cockpit_issues_order_newest_first_and_scoped_shape_matches() -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    newer_target = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    older = _engagement(
        target=target,
        topic=topic,
        status=EngagementStatus.ACTIVE.value,
        created_at=_now() - timedelta(hours=3),
        updated_at=_now() - timedelta(hours=3),
    )
    newer = _engagement(
        target=newer_target,
        status=EngagementStatus.ACTIVE.value,
        created_at=_now() - timedelta(hours=1),
        updated_at=_now() - timedelta(minutes=5),
    )
    failed_candidate = _candidate(
        uuid4(),
        target.community,
        topic,
        status=EngagementCandidateStatus.FAILED.value,
        created_at=_now() - timedelta(hours=2),
        updated_at=_now() - timedelta(hours=2),
    )
    db = FakeDb(
        targets=[target, newer_target],
        topics=[topic],
        engagements=[older, newer],
        candidates=[failed_candidate],
    )

    global_queue = await get_engagement_cockpit_issues(db)  # type: ignore[arg-type]
    scoped_queue = await get_engagement_cockpit_scoped_issues(newer.id, db)  # type: ignore[arg-type]

    assert global_queue.queue_count >= 2
    assert global_queue.current is not None
    assert global_queue.current.engagement_id == newer.id
    assert global_queue.current.issue_type == "topics_not_chosen"
    assert scoped_queue.current is not None
    assert scoped_queue.current.engagement_id == newer.id
    assert scoped_queue.current.issue_type == "topics_not_chosen"


@pytest.mark.asyncio
async def test_cockpit_issues_include_quiet_hours_and_rate_limit_only_for_real_send_blocks() -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    quiet_target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    quiet_engagement = _engagement(target=quiet_target, topic=topic, status=EngagementStatus.ACTIVE.value)
    quiet_account = _account(uuid4())
    quiet_settings = _engagement_settings(
        quiet_engagement.id,
        account_id=quiet_account.id,
        mode=EngagementMode.AUTO_LIMITED.value,
    )
    quiet_settings.quiet_hours_start = (_now() - timedelta(minutes=10)).time().replace(tzinfo=None)
    quiet_settings.quiet_hours_end = (_now() + timedelta(minutes=50)).time().replace(tzinfo=None)
    quiet_candidate = _candidate(uuid4(), quiet_target.community, topic, status=EngagementCandidateStatus.APPROVED.value)

    quiet_db = FakeDb(
        targets=[quiet_target],
        topics=[topic],
        engagements=[quiet_engagement],
        engagement_settings_rows=[quiet_settings],
        memberships=[_membership(community_id=community_id, account_id=quiet_account.id)],
        accounts=[quiet_account],
        candidates=[quiet_candidate],
    )

    quiet_queue = await get_engagement_cockpit_issues(quiet_db)  # type: ignore[arg-type]

    assert quiet_queue.current is not None
    assert quiet_queue.current.issue_type == "quiet_hours_active"

    rate_target = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    rate_topic = _topic(uuid4(), name="Founder replies")
    rate_engagement = _engagement(target=rate_target, topic=rate_topic, status=EngagementStatus.ACTIVE.value)
    rate_account = _account(uuid4(), status=AccountStatus.RATE_LIMITED.value, flood_wait_until=_now() + timedelta(hours=1))
    rate_settings = _engagement_settings(
        rate_engagement.id,
        account_id=rate_account.id,
        mode=EngagementMode.AUTO_LIMITED.value,
    )
    rate_candidate = _candidate(uuid4(), rate_target.community, rate_topic, status=EngagementCandidateStatus.APPROVED.value)
    rate_db = FakeDb(
        targets=[rate_target],
        topics=[rate_topic],
        engagements=[rate_engagement],
        engagement_settings_rows=[rate_settings],
        memberships=[_membership(community_id=rate_target.community_id, account_id=rate_account.id)],
        accounts=[rate_account],
        candidates=[rate_candidate],
    )

    rate_queue = await get_engagement_cockpit_issues(rate_db)  # type: ignore[arg-type]

    assert rate_queue.current is not None
    assert rate_queue.current.issue_type == "rate_limit_active"

@pytest.mark.asyncio
async def test_cockpit_engagement_list_hides_drafts_and_clamps_stale_offset() -> None:
    topic = _topic(uuid4(), name="CRM replies")
    target_a = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    target_b = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    target_c = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    draft = _engagement(target=target_a, status=EngagementStatus.DRAFT.value)
    newer = _engagement(target=target_b, topic=topic, status=EngagementStatus.ACTIVE.value, created_at=_now())
    older = _engagement(
        target=target_c,
        topic=topic,
        status=EngagementStatus.PAUSED.value,
        created_at=_now() - timedelta(days=1),
    )
    db = FakeDb(
        targets=[target_a, target_b, target_c],
        topics=[topic],
        engagements=[draft, older, newer],
        engagement_settings_rows=[
            _engagement_settings(newer.id, account_id=uuid4(), mode=EngagementMode.SUGGEST.value),
            _engagement_settings(older.id, account_id=uuid4(), mode=EngagementMode.AUTO_LIMITED.value),
        ],
    )

    response = await get_engagement_cockpit_engagements(
        db,  # type: ignore[arg-type]
        limit=1,
        offset=99,
    )

    assert response.total == 2
    assert response.offset == 1
    assert len(response.items) == 1
    assert response.items[0].engagement_id == older.id
    assert response.items[0].sending_mode_label == "Auto send"

@pytest.mark.asyncio
async def test_cockpit_engagement_detail_uses_backend_pending_task_priority() -> None:
    community_id = uuid4()
    account_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    settings = _engagement_settings(engagement.id, account_id=account_id, mode=EngagementMode.SUGGEST.value)
    db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        engagement_settings_rows=[settings],
        candidates=[
            _candidate(uuid4(), target.community, topic, status=EngagementCandidateStatus.NEEDS_REVIEW.value),
            _candidate(
                uuid4(),
                target.community,
                topic,
                status=EngagementCandidateStatus.FAILED.value,
                created_at=_now() - timedelta(hours=1),
                updated_at=_now() - timedelta(hours=1),
            ),
        ],
    )

    detail = await get_engagement_cockpit_engagement_detail(engagement.id, db)  # type: ignore[arg-type]

    assert detail.approval_count == 1
    assert detail.issue_count == 2
    assert detail.pending_task is not None
    assert detail.pending_task.task_kind == "approvals"
    assert detail.pending_task.resume_callback == f"eng:appr:eng:{engagement.id}"

@pytest.mark.asyncio
async def test_cockpit_engagement_detail_falls_through_to_issues_when_no_approval_update_state_exists() -> None:
    community_id = uuid4()
    account_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    settings = _engagement_settings(engagement.id, account_id=account_id, mode=EngagementMode.SUGGEST.value)
    membership = _membership(community_id=community_id, account_id=account_id)
    failed_candidate = _candidate(
        uuid4(),
        target.community,
        topic,
        status=EngagementCandidateStatus.FAILED.value,
        final_reply="Try again with a shorter version.",
        operator_notified_at=_now() - timedelta(minutes=10),
        reviewed_at=_now() - timedelta(minutes=5),
    )
    db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        engagement_settings_rows=[settings],
        memberships=[membership],
        candidates=[failed_candidate],
    )

    detail = await get_engagement_cockpit_engagement_detail(engagement.id, db)  # type: ignore[arg-type]

    assert detail.approval_count == 0
    assert detail.issue_count == 1
    assert detail.pending_task is not None
    assert detail.pending_task.task_kind == "issues"
    assert detail.pending_task.resume_callback == f"eng:iss:eng:{engagement.id}"

@pytest.mark.asyncio
async def test_cockpit_sent_feed_orders_newest_first_and_clamps_offset() -> None:
    community = _community(uuid4(), title="Founder Circle")
    newer = _action(
        uuid4(),
        community=community,
        sent_at=_now(),
        outbound_text="Newest reply",
    )
    older = _action(
        uuid4(),
        community=community,
        sent_at=_now() - timedelta(hours=1),
        outbound_text="Older reply",
    )
    db = FakeDb(actions=[older, newer])

    first_page = await get_engagement_cockpit_sent(db, limit=1, offset=0)  # type: ignore[arg-type]
    stale_page = await get_engagement_cockpit_sent(db, limit=1, offset=20)  # type: ignore[arg-type]

    assert first_page.items[0].message_text == "Newest reply"
    assert stale_page.offset == 1
    assert stale_page.items[0].message_text == "Older reply"


@pytest.mark.asyncio
async def test_cockpit_sent_feed_ignores_join_audit_actions() -> None:
    community = _community(uuid4(), title="Founder Circle")
    reply_action = _action(
        uuid4(),
        community=community,
        sent_at=_now(),
        outbound_text="Actual public reply",
    )
    join_action = _action(
        uuid4(),
        community=community,
        sent_at=_now() + timedelta(minutes=1),
        outbound_text=None,
    )
    join_action.action_type = "join"
    db = FakeDb(actions=[reply_action, join_action])

    response = await get_engagement_cockpit_sent(db, limit=20, offset=0)  # type: ignore[arg-type]

    assert response.total == 1
    assert response.items[0].message_text == "Actual public reply"


@pytest.mark.asyncio
async def test_post_engagement_cockpit_draft_edit_creates_durable_update_state() -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    candidate = _candidate(uuid4(), target.community, topic)
    db = FakeDb(targets=[target], topics=[topic], engagements=[engagement], candidates=[candidate])

    response = await post_engagement_cockpit_draft_edit(
        candidate.id,
        CockpitDraftEditRequest(edit_request="Make it shorter", requested_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )
    queue = await get_engagement_cockpit_approvals(db)  # type: ignore[arg-type]

    assert response.result == "queued_update"
    assert response.next_callback == "eng:appr:list:0"
    assert db.commits == 1
    assert len(db.draft_update_requests) == 1
    assert queue.queue_count == 0
    assert queue.updating_count == 1
    assert queue.empty_state == "waiting_for_updates"


@pytest.mark.asyncio
async def test_complete_draft_update_request_surfaces_updated_replacement_draft_in_approvals() -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    source_candidate = _candidate(uuid4(), target.community, topic)
    replacement_candidate = _candidate(
        uuid4(),
        target.community,
        topic,
        suggested_reply="Here is a tighter reply with less sales language.",
        created_at=_now() + timedelta(minutes=2),
        updated_at=_now() + timedelta(minutes=2),
    )
    request = _draft_update_request(
        engagement_id=engagement.id,
        source_candidate_id=source_candidate.id,
        status="pending",
        source_queue_created_at=source_candidate.created_at,
    )
    db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        candidates=[source_candidate, replacement_candidate],
        draft_update_requests=[request],
    )

    completed = await complete_draft_update_request(
        db,  # type: ignore[arg-type]
        source_candidate_id=source_candidate.id,
        replacement_candidate_id=replacement_candidate.id,
    )
    queue = await get_engagement_cockpit_approvals(db)  # type: ignore[arg-type]

    assert completed is request
    assert request.status == "completed"
    assert request.replacement_candidate_id == replacement_candidate.id
    assert request.completed_at is not None
    assert request.updated_at == request.completed_at
    assert db.flushes == 1
    assert queue.queue_count == 1
    assert queue.updating_count == 0
    assert queue.empty_state == "none"
    assert queue.current is not None
    assert queue.current.draft_id == replacement_candidate.id
    assert queue.current.badge == "Updated draft"


@pytest.mark.asyncio
async def test_complete_draft_update_request_keeps_placeholder_when_replacement_draft_is_invalid() -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    other_topic = _topic(uuid4(), name="Founder replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    source_candidate = _candidate(uuid4(), target.community, topic)
    replacement_candidate = _candidate(
        uuid4(),
        target.community,
        other_topic,
        created_at=_now() + timedelta(minutes=2),
        updated_at=_now() + timedelta(minutes=2),
    )
    request = _draft_update_request(
        engagement_id=engagement.id,
        source_candidate_id=source_candidate.id,
        status="pending",
        source_queue_created_at=source_candidate.created_at,
    )
    db = FakeDb(
        targets=[target],
        topics=[topic, other_topic],
        engagements=[engagement],
        candidates=[source_candidate, replacement_candidate],
        draft_update_requests=[request],
    )

    completed = await complete_draft_update_request(
        db,  # type: ignore[arg-type]
        source_candidate_id=source_candidate.id,
        replacement_candidate_id=replacement_candidate.id,
    )
    queue = await get_engagement_cockpit_approvals(db)  # type: ignore[arg-type]

    assert completed is None
    assert request.status == "pending"
    assert request.replacement_candidate_id is None
    assert request.completed_at is None
    assert db.flushes == 0
    assert queue.queue_count == 0
    assert queue.updating_count == 1
    assert queue.empty_state == "waiting_for_updates"


@pytest.mark.asyncio
async def test_post_engagement_cockpit_draft_approve_and_reject_return_semantic_results() -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    approve_candidate_row = _candidate(uuid4(), target.community, topic)
    reject_candidate_row = _candidate(uuid4(), target.community, topic)

    approve_db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        candidates=[approve_candidate_row],
        candidate=approve_candidate_row,
    )
    approve_response = await post_engagement_cockpit_draft_approve(
        approve_candidate_row.id,
        approve_db,  # type: ignore[arg-type]
    )

    reject_db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        candidates=[reject_candidate_row],
        candidate=reject_candidate_row,
    )
    reject_response = await post_engagement_cockpit_draft_reject(
        reject_candidate_row.id,
        reject_db,  # type: ignore[arg-type]
    )

    assert approve_response.result == "approved"
    assert approve_candidate_row.status == EngagementCandidateStatus.APPROVED.value
    assert approve_db.commits == 1
    assert reject_response.result == "rejected"
    assert reject_candidate_row.status == EngagementCandidateStatus.REJECTED.value
    assert reject_db.commits == 1


@pytest.mark.asyncio
async def test_post_engagement_cockpit_issue_action_returns_next_step_and_resolved_results() -> None:
    quiet_topic = _topic(uuid4(), name="CRM replies")
    quiet_target = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    quiet_engagement = _engagement(target=quiet_target, topic=quiet_topic, status=EngagementStatus.ACTIVE.value)
    quiet_account = _account(uuid4())
    quiet_settings = _engagement_settings(
        quiet_engagement.id,
        account_id=quiet_account.id,
        mode=EngagementMode.AUTO_LIMITED.value,
    )
    quiet_settings.quiet_hours_start = (_now() - timedelta(minutes=10)).time().replace(tzinfo=None)
    quiet_settings.quiet_hours_end = (_now() + timedelta(minutes=50)).time().replace(tzinfo=None)
    quiet_candidate = _candidate(uuid4(), quiet_target.community, quiet_topic, status=EngagementCandidateStatus.APPROVED.value)
    quiet_db = FakeDb(
        targets=[quiet_target],
        topics=[quiet_topic],
        engagements=[quiet_engagement],
        engagement_settings_rows=[quiet_settings],
        memberships=[_membership(community_id=quiet_target.community_id, account_id=quiet_account.id)],
        accounts=[quiet_account],
        candidates=[quiet_candidate],
    )
    quiet_issue_id = (await get_engagement_cockpit_issues(quiet_db)).current.issue_id  # type: ignore[union-attr]

    quiet_response = await post_engagement_cockpit_issue_action(
        quiet_issue_id,
        "quiet",
        quiet_db,  # type: ignore[arg-type]
    )

    paused_topic = _topic(uuid4(), name="Founder replies")
    paused_target = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    paused_engagement = _engagement(target=paused_target, topic=paused_topic, status=EngagementStatus.PAUSED.value)
    paused_account = _account(uuid4())
    paused_settings = _engagement_settings(
        paused_engagement.id,
        account_id=paused_account.id,
        mode=EngagementMode.SUGGEST.value,
    )
    paused_db = FakeDb(
        targets=[paused_target],
        topics=[paused_topic],
        engagements=[paused_engagement],
        engagement_settings_rows=[paused_settings],
        memberships=[_membership(community_id=paused_target.community_id, account_id=paused_account.id)],
        accounts=[paused_account],
    )
    paused_issue_id = (await get_engagement_cockpit_issues(paused_db)).current.issue_id  # type: ignore[union-attr]

    resume_response = await post_engagement_cockpit_issue_action(
        paused_issue_id,
        "resume",
        paused_db,  # type: ignore[arg-type]
    )

    assert quiet_response.result == "next_step"
    assert quiet_response.next_callback == f"eng:quiet:open:{quiet_engagement.id}:{quiet_issue_id}"
    assert resume_response.result == "resolved"
    assert paused_engagement.status == EngagementStatus.ACTIVE.value
    assert paused_db.commits == 1


@pytest.mark.asyncio
async def test_post_engagement_cockpit_issue_action_retry_reopens_failed_candidate() -> None:
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    account = _account(uuid4())
    settings = _engagement_settings(engagement.id, account_id=account.id, mode=EngagementMode.SUGGEST.value)
    membership = _membership(community_id=target.community_id, account_id=account.id)
    candidate = _candidate(
        uuid4(),
        target.community,
        topic,
        status=EngagementCandidateStatus.FAILED.value,
        final_reply="Short follow-up reply.",
        created_at=_now() - timedelta(minutes=15),
        updated_at=_now() - timedelta(minutes=15),
    )
    db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        engagement_settings_rows=[settings],
        memberships=[membership],
        accounts=[account],
        candidates=[candidate],
        candidate=candidate,
    )
    issue_id = (await get_engagement_cockpit_issues(db)).current.issue_id  # type: ignore[union-attr]

    response = await post_engagement_cockpit_issue_action(
        issue_id,
        "retry",
        db,  # type: ignore[arg-type]
    )

    assert response.result == "resolved"
    assert response.message == "Reply reopened"
    assert candidate.status == EngagementCandidateStatus.NEEDS_REVIEW.value
    assert db.commits == 1


@pytest.mark.asyncio
async def test_post_engagement_cockpit_issue_action_apptgt_approves_target_from_resolved_state() -> None:
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(uuid4(), status=EngagementTargetStatus.RESOLVED.value)
    target.allow_join = False
    target.allow_detect = False
    target.allow_post = False
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    account = _account(uuid4())
    settings = _engagement_settings(engagement.id, account_id=account.id, mode=EngagementMode.AUTO_LIMITED.value)
    membership = _membership(community_id=target.community_id, account_id=account.id)
    db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        engagement_settings_rows=[settings],
        memberships=[membership],
        accounts=[account],
    )
    issue_id = (await get_engagement_cockpit_issues(db)).current.issue_id  # type: ignore[union-attr]

    response = await post_engagement_cockpit_issue_action(
        issue_id,
        "apptgt",
        db,  # type: ignore[arg-type]
    )

    assert response.result == "resolved"
    assert response.message == "Target approved"
    assert target.status == EngagementTargetStatus.APPROVED.value
    assert target.allow_join is True
    assert target.allow_detect is True
    assert target.allow_post is True
    assert target.approved_by == "operator"
    assert target.approved_at is not None
    assert db.commits == 1


@pytest.mark.asyncio
async def test_post_engagement_cockpit_issue_action_rsvtgt_enqueues_resolution_job() -> None:
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(uuid4(), status=EngagementTargetStatus.PENDING.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    account = _account(uuid4())
    settings = _engagement_settings(engagement.id, account_id=account.id, mode=EngagementMode.SUGGEST.value)
    membership = _membership(community_id=target.community_id, account_id=account.id)
    db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        engagement_settings_rows=[settings],
        memberships=[membership],
        accounts=[account],
    )
    captured: dict[str, object] = {}

    def fake_enqueue(target_id: object, *, requested_by: str) -> QueuedJob:
        captured.update({"target_id": target_id, "requested_by": requested_by})
        return QueuedJob(id="resolve-job", type="engagement_target.resolve")

    issue_id = (await get_engagement_cockpit_issues(db)).current.issue_id  # type: ignore[union-attr]

    from backend.api.routes import engagement as engagement_routes

    original_enqueue = engagement_routes.enqueue_engagement_target_resolve
    engagement_routes.enqueue_engagement_target_resolve = fake_enqueue
    try:
        response = await post_engagement_cockpit_issue_action(
            issue_id,
            "rsvtgt",
            db,  # type: ignore[arg-type]
        )
    finally:
        engagement_routes.enqueue_engagement_target_resolve = original_enqueue

    assert response.result == "resolved"
    assert response.message == "Target resolution started"
    assert captured == {"target_id": target.id, "requested_by": "operator"}
    assert db.commits == 1


@pytest.mark.asyncio
async def test_post_engagement_cockpit_issue_action_fixperm_syncs_target_and_settings() -> None:
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    target.allow_detect = False
    target.allow_post = False
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    account = _account(uuid4())
    settings = _engagement_settings(engagement.id, account_id=account.id, mode=EngagementMode.AUTO_LIMITED.value)
    settings.allow_post = False
    membership = _membership(community_id=target.community_id, account_id=account.id)
    db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        engagement_settings_rows=[settings],
        memberships=[membership],
        accounts=[account],
    )
    issue_id = (await get_engagement_cockpit_issues(db)).current.issue_id  # type: ignore[union-attr]

    response = await post_engagement_cockpit_issue_action(
        issue_id,
        "fixperm",
        db,  # type: ignore[arg-type]
    )

    assert response.result == "resolved"
    assert response.message == "Permissions fixed"
    assert settings.allow_join is True
    assert settings.allow_post is True
    assert target.allow_join is True
    assert target.allow_detect is True
    assert target.allow_post is True
    assert db.commits == 1


@pytest.mark.asyncio
async def test_cockpit_rate_limit_detail_and_quiet_hours_read_write_routes_use_semantic_shapes() -> None:
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    account = _account(uuid4(), status=AccountStatus.RATE_LIMITED.value, flood_wait_until=_now() + timedelta(hours=1))
    settings = _engagement_settings(
        engagement.id,
        account_id=account.id,
        mode=EngagementMode.AUTO_LIMITED.value,
    )
    settings.quiet_hours_start = (_now() - timedelta(minutes=10)).time().replace(tzinfo=None)
    settings.quiet_hours_end = (_now() + timedelta(minutes=50)).time().replace(tzinfo=None)
    approved_candidate = _candidate(uuid4(), target.community, topic, status=EngagementCandidateStatus.APPROVED.value)
    db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        engagement_settings_rows=[settings],
        memberships=[_membership(community_id=target.community_id, account_id=account.id)],
        accounts=[account],
        candidates=[approved_candidate],
    )

    quiet_issue = (await get_engagement_cockpit_issues(db)).current  # type: ignore[assignment]
    quiet_read = await get_engagement_cockpit_quiet_hours(engagement.id, db)  # type: ignore[arg-type]
    quiet_write = await put_engagement_cockpit_quiet_hours(
        engagement.id,
        CockpitQuietHoursWriteRequest(quiet_hours_enabled=False),
        db,  # type: ignore[arg-type]
    )

    rate_settings = _engagement_settings(
        engagement.id,
        account_id=account.id,
        mode=EngagementMode.AUTO_LIMITED.value,
    )
    rate_db = FakeDb(
        targets=[target],
        topics=[topic],
        engagements=[engagement],
        engagement_settings_rows=[rate_settings],
        memberships=[_membership(community_id=target.community_id, account_id=account.id)],
        accounts=[account],
        candidates=[approved_candidate],
    )
    rate_issue = (await get_engagement_cockpit_issues(rate_db)).current  # type: ignore[assignment]
    rate_detail = await get_engagement_cockpit_issue_rate_limit(rate_issue.issue_id, rate_db)  # type: ignore[arg-type]

    assert quiet_issue is not None
    assert quiet_read.result == "ready"
    assert quiet_read.next_callback == f"eng:iss:open:{quiet_issue.issue_id}"
    assert quiet_write.result == "updated"
    assert quiet_write.next_callback == "eng:iss:list:0"
    assert quiet_write.quiet_hours_enabled is False
    assert db.commits == 1
    assert rate_issue is not None
    assert rate_detail.result == "ready"
    assert rate_detail.issue_id == rate_issue.issue_id
    assert rate_detail.next_callback == f"eng:iss:open:{rate_issue.issue_id}"

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
async def test_duplicate_engagement_target_creates_new_row() -> None:
    target = _target(uuid4(), status=EngagementTargetStatus.PENDING.value)
    target.community_id = None
    target.submitted_ref = "username:example"
    target.submitted_ref_type = EngagementTargetRefType.TELEGRAM_USERNAME.value
    db = FakeDb(target=target)

    response = await post_engagement_target(
        EngagementTargetCreateRequest(target_ref="@example", added_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.id != target.id
    assert len(db.added) == 1
    assert isinstance(db.added[0], EngagementTarget)
    assert db.added[0].submitted_ref == "username:example"
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
        communities: list[Community] | None = None,
        settings: CommunityEngagementSettings | None = None,
        engagement: Engagement | None = None,
        engagements: list[Engagement] | None = None,
        engagement_settings: EngagementSettings | None = None,
        engagement_settings_rows: list[EngagementSettings] | None = None,
        draft_update_requests: list[EngagementDraftUpdateRequest] | None = None,
        membership: CommunityAccountMembership | None = None,
        memberships: list[CommunityAccountMembership] | None = None,
        topic: EngagementTopic | None = None,
        topics: list[EngagementTopic] | None = None,
        style_rule: EngagementStyleRule | None = None,
        target: EngagementTarget | None = None,
        targets: list[EngagementTarget] | None = None,
        candidate: EngagementCandidate | None = None,
        candidates: list[EngagementCandidate] | None = None,
        revisions: list[EngagementCandidateRevision] | None = None,
        actions: list[EngagementAction] | None = None,
        account: TelegramAccount | None = None,
        accounts: list[TelegramAccount] | None = None,
        scalar_result: object | None = None,
    ) -> None:
        self.community = community
        self.communities = list(communities or ([] if community is None else [community]))
        self.settings = settings
        self.engagement = engagement
        self.engagements = list(engagements or ([] if engagement is None else [engagement]))
        self.engagement_settings = engagement_settings
        self.engagement_settings_rows = list(
            engagement_settings_rows or ([] if engagement_settings is None else [engagement_settings])
        )
        self.draft_update_requests = list(draft_update_requests or [])
        self.membership = membership
        self.memberships = list(memberships or ([] if membership is None else [membership]))
        self.topic = topic
        self.topics = list(topics or ([] if topic is None else [topic]))
        self.style_rule = style_rule
        self.target = target
        self.targets = list(targets or ([] if target is None else [target]))
        self.candidate = candidate
        self.candidates = list(candidates or ([] if candidate is None else [candidate]))
        self.revisions = revisions
        self.actions = list(actions or [])
        self.account = account
        self.accounts = list(accounts or ([] if account is None else [account]))
        self.scalar_result = scalar_result
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0

    async def get(self, model: object, item_id: object) -> object | None:
        if model is Community:
            return self._lookup(self.communities, item_id, self.community)
        if model is Engagement:
            return self._lookup(self.engagements, item_id, self.engagement)
        if model is EngagementSettings:
            return self._lookup(self.engagement_settings_rows, item_id, self.engagement_settings, key="engagement_id")
        if model is EngagementDraftUpdateRequest:
            return self._lookup(self.draft_update_requests, item_id, None)
        if model is CommunityAccountMembership:
            return self._lookup(self.memberships, item_id, self.membership)
        if model is EngagementTopic:
            return self._lookup(self.topics, item_id, self.topic)
        if model is EngagementStyleRule:
            return self.style_rule
        if model is EngagementTarget:
            return self._lookup(self.targets, item_id, self.target)
        if model is EngagementCandidate:
            return self._lookup(self.candidates, item_id, self.candidate)
        if model is TelegramAccount:
            return self._lookup(self.accounts, item_id, self.account)
        return None

    async def scalar(self, statement: object) -> object | None:
        if self.scalar_result is not None:
            return self.scalar_result
        model_name = _selected_model_name(statement)
        if model_name == "CommunityEngagementSettings":
            return self.settings
        if model_name == "Engagement":
            return self.engagement if self.engagement is not None else (self.engagements[0] if self.engagements else None)
        if model_name == "EngagementSettings":
            return self.engagement_settings if self.engagement_settings is not None else (
                self.engagement_settings_rows[0] if self.engagement_settings_rows else None
            )
        if model_name == "EngagementDraftUpdateRequest":
            return self.draft_update_requests[0] if self.draft_update_requests else None
        if model_name == "CommunityAccountMembership":
            return self.membership if self.membership is not None else (self.memberships[0] if self.memberships else None)
        if model_name == "EngagementTopic":
            return self.topic if self.topic is not None else (self.topics[0] if self.topics else None)
        if model_name == "EngagementStyleRule":
            return self.style_rule
        if model_name == "EngagementTarget":
            return self.target if self.target is not None else (self.targets[0] if self.targets else None)
        if model_name == "EngagementCandidate":
            return self.candidate if self.candidate is not None else (self.candidates[0] if self.candidates else None)
        if model_name == "TelegramAccount":
            return self.account if self.account is not None else (self.accounts[0] if self.accounts else None)
        if self.target is not None:
            return self.target
        if self.candidates:
            return len(self.candidates)
        if self.actions:
            return len(self.actions)
        return self.settings

    async def scalars(self, statement: object) -> list[object]:
        model_name = _selected_model_name(statement)
        if self.revisions is not None:
            return list(self.revisions)
        if model_name == "Community":
            return list(self.communities)
        if model_name == "Engagement":
            return list(self.engagements)
        if model_name == "EngagementSettings":
            return list(self.engagement_settings_rows)
        if model_name == "EngagementDraftUpdateRequest":
            return list(self.draft_update_requests)
        if model_name == "CommunityAccountMembership":
            return list(self.memberships)
        if model_name == "EngagementTopic":
            return list(self.topics)
        if model_name == "EngagementTarget":
            return list(self.targets)
        if model_name == "TelegramAccount":
            return list(self.accounts)
        if model_name == "EngagementAction":
            return list(self.actions)
        return list(self.candidates or [])

    def add(self, model: object) -> None:
        self.added.append(model)
        if isinstance(model, EngagementDraftUpdateRequest):
            self.draft_update_requests.append(model)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    @staticmethod
    def _lookup(items: list[object], item_id: object, fallback: object | None, *, key: str = "id") -> object | None:
        for item in items:
            if getattr(item, key, None) == item_id:
                return item
        return fallback


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
    name: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Engagement:
    engagement = Engagement(
        id=uuid4(),
        target_id=target.id,
        community_id=target.community_id,
        topic_id=None if topic is None else topic.id,
        status=status,
        name=name,
        created_by="telegram:123",
        created_at=created_at or _now(),
        updated_at=updated_at or created_at or _now(),
    )
    engagement.target = target
    engagement.community = target.community
    if topic is not None:
        engagement.topic = topic
    return engagement


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


def _account(
    account_id: object,
    *,
    phone: str = "+123456789",
    status: str = AccountStatus.AVAILABLE.value,
    account_pool: str = AccountPool.ENGAGEMENT.value,
    flood_wait_until: datetime | None = None,
) -> TelegramAccount:
    return TelegramAccount(
        id=account_id,
        phone=phone,
        session_file_path="engagement.session",
        account_pool=account_pool,
        status=status,
        flood_wait_until=flood_wait_until,
    )


def _draft_update_request(
    *,
    engagement_id: object,
    source_candidate_id: object,
    status: str = "pending",
    replacement_candidate_id: object | None = None,
    source_queue_created_at: datetime | None = None,
) -> EngagementDraftUpdateRequest:
    return EngagementDraftUpdateRequest(
        id=uuid4(),
        engagement_id=engagement_id,
        source_candidate_id=source_candidate_id,
        replacement_candidate_id=replacement_candidate_id,
        status=status,
        edit_request="Make it shorter",
        requested_by="telegram:123",
        source_queue_created_at=source_queue_created_at or _now(),
        created_at=_now(),
        updated_at=_now(),
        completed_at=_now() if status == "completed" else None,
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
    status: str = EngagementCandidateStatus.NEEDS_REVIEW.value,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    detected_reason: str | None = None,
    suggested_reply: str | None = None,
    final_reply: str | None = None,
    operator_notified_at: datetime | None = None,
    reviewed_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> EngagementCandidate:
    candidate = EngagementCandidate(
        id=candidate_id,
        community_id=community.id,
        topic_id=topic.id,
        source_tg_message_id=123,
        source_excerpt="The group is comparing CRM tools.",
        source_message_date=_now() - timedelta(minutes=30),
        detected_at=(created_at or _now()) - timedelta(minutes=25),
        detected_reason=detected_reason or "The group is comparing CRM alternatives.",
        moment_strength="good",
        timeliness="fresh",
        reply_value="practical_tip",
        suggested_reply=suggested_reply or "Compare data ownership, integrations, and exit paths first.",
        risk_notes=[],
        status=status,
        final_reply=final_reply,
        reviewed_at=reviewed_at,
        review_deadline_at=_now() + timedelta(minutes=30),
        reply_deadline_at=_now() + timedelta(minutes=60),
        operator_notified_at=operator_notified_at,
        expires_at=expires_at or datetime(2999, 4, 20, tzinfo=timezone.utc),
        created_at=created_at or _now(),
        updated_at=updated_at or created_at or _now(),
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


def _action(
    action_id: object,
    *,
    community: Community,
    sent_at: datetime | None = None,
    outbound_text: str | None = None,
    status: str = "sent",
    created_at: datetime | None = None,
) -> EngagementAction:
    action = EngagementAction(
        id=action_id,
        candidate_id=None,
        community_id=community.id,
        telegram_account_id=uuid4(),
        action_type="reply",
        status=status,
        idempotency_key=str(action_id),
        outbound_text=outbound_text,
        reply_to_tg_message_id=123,
        sent_tg_message_id=456,
        scheduled_at=created_at or _now(),
        sent_at=sent_at,
        error_message=None,
        created_at=created_at or _now(),
        updated_at=sent_at or created_at or _now(),
    )
    action.community = community
    return action


def _now() -> datetime:
    return _FIXTURE_NOW
