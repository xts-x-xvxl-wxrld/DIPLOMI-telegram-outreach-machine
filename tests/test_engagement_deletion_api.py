from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.api.routes.engagement import (
    delete_engagement_topic,
    delete_task_first_engagement,
    patch_engagement_topic,
    post_task_first_engagement,
)
from backend.api.schemas import EngagementTopicUpdate, TaskFirstEngagementCreateRequest
from backend.db.enums import (
    EngagementCandidateStatus,
    EngagementMode,
    EngagementStatus,
    EngagementTargetStatus,
)
from backend.db.models import EngagementCandidate, EngagementSettings, EngagementTopic
from tests.test_engagement_api import FakeDb, _engagement, _now, _target, _topic


@pytest.mark.asyncio
async def test_update_topic_allows_research_guidance() -> None:
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
            created_at=_now(),
            updated_at=_now(),
        )
    )

    response = await patch_engagement_topic(
        topic_id,
        EngagementTopicUpdate(stance_guidance="Create fake consensus."),
        db,  # type: ignore[arg-type]
    )

    assert response.stance_guidance == "Create fake consensus."


@pytest.mark.asyncio
async def test_delete_topic_blocks_when_visible_engagement_uses_it() -> None:
    topic = _topic(uuid4(), name="CRM")
    target = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    db = FakeDb(topic=topic, engagement=engagement)

    with pytest.raises(HTTPException) as exc_info:
        await delete_engagement_topic(topic.id, db)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "topic_in_use"
    assert db.commits == 0


@pytest.mark.asyncio
async def test_delete_topic_archives_when_history_exists() -> None:
    topic = _topic(uuid4(), name="CRM")
    archived_target = _target(uuid4(), status=EngagementTargetStatus.ARCHIVED.value)
    archived_engagement = _engagement(target=archived_target, topic=topic, status=EngagementStatus.ARCHIVED.value)
    candidate = EngagementCandidate(
        id=uuid4(),
        community_id=archived_target.community_id,
        topic_id=topic.id,
        detected_at=_now(),
        detected_reason="Matched topic",
        moment_strength="good",
        timeliness="fresh",
        reply_value="practical_tip",
        status=EngagementCandidateStatus.SENT.value,
        reply_deadline_at=_now(),
        expires_at=_now() + timedelta(hours=1),
        created_at=_now(),
        updated_at=_now(),
    )
    db = FakeDb(topic=topic, engagements=[archived_engagement], candidates=[candidate])

    response = await delete_engagement_topic(topic.id, db)  # type: ignore[arg-type]

    assert response.result == "archived"
    assert topic.active is False
    assert db.commits == 1


@pytest.mark.asyncio
async def test_delete_draft_task_first_engagement_hard_deletes_when_no_history() -> None:
    target = _target(uuid4(), status=EngagementTargetStatus.RESOLVED.value)
    topic = _topic(uuid4(), name="CRM")
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.DRAFT.value)
    settings = EngagementSettings(
        id=uuid4(),
        engagement_id=engagement.id,
        mode=EngagementMode.SUGGEST.value,
        allow_join=True,
        allow_post=False,
        reply_only=True,
        require_approval=True,
        max_posts_per_day=1,
        min_minutes_between_posts=240,
        assigned_account_id=None,
        created_at=_now(),
        updated_at=_now(),
    )
    db = FakeDb(target=target, engagement=engagement, engagement_settings=settings)

    response = await delete_task_first_engagement(engagement.id, db)  # type: ignore[arg-type]

    assert response.result == "deleted"
    assert engagement not in db.engagements
    assert settings not in db.engagement_settings_rows
    assert target.allow_join is False
    assert db.commits == 1


@pytest.mark.asyncio
async def test_delete_active_task_first_engagement_archives_and_disables_target() -> None:
    target = _target(uuid4(), status=EngagementTargetStatus.APPROVED.value)
    topic = _topic(uuid4(), name="CRM")
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    settings = EngagementSettings(
        id=uuid4(),
        engagement_id=engagement.id,
        mode=EngagementMode.AUTO_LIMITED.value,
        allow_join=True,
        allow_post=True,
        reply_only=True,
        require_approval=True,
        max_posts_per_day=1,
        min_minutes_between_posts=240,
        assigned_account_id=uuid4(),
        created_at=_now(),
        updated_at=_now(),
    )
    candidate = EngagementCandidate(
        id=uuid4(),
        community_id=engagement.community_id,
        topic_id=topic.id,
        detected_at=_now(),
        detected_reason="Matched topic",
        moment_strength="good",
        timeliness="fresh",
        reply_value="practical_tip",
        status=EngagementCandidateStatus.APPROVED.value,
        reply_deadline_at=_now(),
        expires_at=_now() + timedelta(hours=1),
        created_at=_now(),
        updated_at=_now(),
    )
    db = FakeDb(
        target=target,
        engagement=engagement,
        engagement_settings=settings,
        candidates=[candidate],
    )

    response = await delete_task_first_engagement(engagement.id, db)  # type: ignore[arg-type]

    assert response.result == "archived"
    assert engagement.status == EngagementStatus.ARCHIVED.value
    assert settings.mode == EngagementMode.DISABLED.value
    assert target.status == EngagementTargetStatus.ARCHIVED.value
    assert target.allow_detect is False
    assert db.commits == 1


@pytest.mark.asyncio
async def test_create_task_first_engagement_reopens_archived_existing_row() -> None:
    target = _target(uuid4(), status=EngagementTargetStatus.ARCHIVED.value)
    topic = _topic(uuid4(), name="CRM")
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ARCHIVED.value)
    settings = EngagementSettings(
        id=uuid4(),
        engagement_id=engagement.id,
        mode=EngagementMode.AUTO_LIMITED.value,
        allow_join=True,
        allow_post=True,
        reply_only=True,
        require_approval=True,
        max_posts_per_day=1,
        min_minutes_between_posts=240,
        assigned_account_id=uuid4(),
        created_at=_now(),
        updated_at=_now(),
    )
    db = FakeDb(target=target, engagement=engagement, engagement_settings=settings)

    response = await post_task_first_engagement(
        TaskFirstEngagementCreateRequest(target_id=target.id, created_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.result == "reopened"
    assert response.engagement.status == EngagementStatus.DRAFT.value
    assert response.engagement.topic_id is None
    assert settings.mode == EngagementMode.DISABLED.value
    assert settings.assigned_account_id is None
    assert target.status == EngagementTargetStatus.RESOLVED.value
    assert db.commits == 1
