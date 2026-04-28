from __future__ import annotations

from uuid import uuid4

import pytest

from backend.api.routes.engagement import post_task_first_wizard_confirm
from backend.api.schemas import TaskFirstWizardActionRequest
from backend.db.enums import EngagementMode, EngagementStatus, EngagementTargetStatus
from backend.queue.client import QueuedJob
from tests.test_engagement_api import (
    FakeDb,
    _engagement,
    _engagement_settings,
    _membership,
    _target,
    _topic,
)


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
async def test_task_first_wizard_confirm_enqueues_join_for_unjoined_account(monkeypatch) -> None:
    community_id = uuid4()
    account_id = uuid4()
    target = _target(community_id, status=EngagementTargetStatus.RESOLVED.value)
    topic = _topic(uuid4(), name="CRM")
    engagement = _engagement(target=target, topic=topic)
    settings = _engagement_settings(engagement.id, account_id=account_id, mode=EngagementMode.SUGGEST.value)
    db = FakeDb(target=target, engagement=engagement, topic=topic, engagement_settings=settings)
    join_calls: list[dict[str, object]] = []

    def fake_enqueue_join(*, community_id, telegram_account_id, requested_by):
        join_calls.append(
            {
                "community_id": community_id,
                "telegram_account_id": telegram_account_id,
                "requested_by": requested_by,
            }
        )
        return QueuedJob(id="join-job", type="community.join")

    def fake_enqueue_detect(community_id_arg, *, window_minutes, requested_by):
        return QueuedJob(id="detect-job", type="engagement.detect")

    monkeypatch.setattr("backend.services.task_first_engagements.enqueue_community_join", fake_enqueue_join)
    monkeypatch.setattr("backend.api.routes.engagement.enqueue_manual_engagement_detect", fake_enqueue_detect)

    response = await post_task_first_wizard_confirm(
        engagement.id,
        TaskFirstWizardActionRequest(requested_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.result == "confirmed"
    assert join_calls == [
        {
            "community_id": community_id,
            "telegram_account_id": account_id,
            "requested_by": "telegram:123",
        }
    ]
    assert response.engagement_status == EngagementStatus.ACTIVE.value


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

    def fake_enqueue(community_id_arg: object, *, window_minutes: int, requested_by: str) -> QueuedJob:
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
