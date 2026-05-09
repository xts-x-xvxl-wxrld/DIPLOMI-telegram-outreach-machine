from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.api.routes.engagement_cockpit import get_engagement_cockpit_approvals, post_engagement_cockpit_draft_edit
from backend.api.schemas import CockpitDraftEditRequest
from backend.db.enums import EngagementStatus, EngagementTargetStatus
from backend.queue.client import QueuedJob, QueueUnavailable
from tests.test_engagement_api import FakeDb, _candidate, _engagement, _target, _topic


@pytest.mark.asyncio
async def test_post_engagement_cockpit_draft_edit_creates_durable_update_state(monkeypatch) -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    candidate = _candidate(uuid4(), target.community, topic)
    db = FakeDb(targets=[target], topics=[topic], engagements=[engagement], candidates=[candidate])

    def fake_enqueue(*args: object, **kwargs: object) -> QueuedJob:
        return QueuedJob(id="rewrite-job", type="engagement.detect")

    monkeypatch.setattr("backend.api.routes.engagement_cockpit.enqueue_engagement_detect", fake_enqueue)

    response = await post_engagement_cockpit_draft_edit(
        candidate.id,
        CockpitDraftEditRequest(edit_request="Make it shorter", requested_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )
    queue = await get_engagement_cockpit_approvals(db)  # type: ignore[arg-type]

    assert response.result == "queued_update"
    assert response.next_callback == "eng:appr:list:0"
    assert response.job_id == "rewrite-job"
    assert response.job_type == "engagement.detect"
    assert db.commits == 1
    assert len(db.draft_update_requests) == 1
    assert queue.queue_count == 0
    assert queue.updating_count == 1
    assert queue.empty_state == "waiting_for_updates"


@pytest.mark.asyncio
async def test_post_engagement_cockpit_draft_edit_rolls_back_when_enqueue_fails(monkeypatch) -> None:
    community_id = uuid4()
    topic = _topic(uuid4(), name="CRM replies")
    target = _target(community_id, status=EngagementTargetStatus.APPROVED.value)
    engagement = _engagement(target=target, topic=topic, status=EngagementStatus.ACTIVE.value)
    candidate = _candidate(uuid4(), target.community, topic)
    db = FakeDb(targets=[target], topics=[topic], engagements=[engagement], candidates=[candidate])

    def fake_enqueue(*args: object, **kwargs: object) -> QueuedJob:
        raise QueueUnavailable("redis unavailable")

    monkeypatch.setattr("backend.api.routes.engagement_cockpit.enqueue_engagement_detect", fake_enqueue)

    with pytest.raises(HTTPException) as exc_info:
        await post_engagement_cockpit_draft_edit(
            candidate.id,
            CockpitDraftEditRequest(edit_request="Make it shorter", requested_by="telegram:123"),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "redis unavailable"
    assert db.commits == 0
    assert db.rollbacks == 1
