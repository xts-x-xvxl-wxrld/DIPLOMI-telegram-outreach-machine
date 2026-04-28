from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.api.routes.engagement import (
    get_engagement_actions,
    get_engagement_candidate_detail,
    get_engagement_candidate_revisions,
    get_engagement_candidates,
    get_engagement_semantic_rollout,
    post_engagement_candidate_approve,
    post_engagement_candidate_edit,
    post_engagement_candidate_expire,
    post_engagement_candidate_reject,
    post_engagement_candidate_retry,
    post_engagement_candidate_send_job,
)
from backend.api.schemas import (
    EngagementCandidateApproveRequest,
    EngagementCandidateEditRequest,
    EngagementCandidateExpireRequest,
    EngagementCandidateRejectRequest,
    EngagementCandidateRetryRequest,
    EngagementSendJobRequest,
)
from backend.db.enums import (
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
)
from backend.db.models import EngagementAction, EngagementCandidateRevision
from backend.queue.client import QueuedJob
from backend.services.community_engagement import EngagementActionListResult, EngagementActionView
from tests.engagement_api_helpers import FakeDb, _candidate, _community, _now, _topic


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
async def test_semantic_rollout_summary_groups_operator_outcomes_by_similarity_band() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    approved = _candidate(uuid4(), community, topic)
    approved.status = EngagementCandidateStatus.APPROVED.value
    approved.model_output = {"semantic_match": {"similarity": 0.83}}
    rejected = _candidate(uuid4(), community, topic)
    rejected.status = EngagementCandidateStatus.REJECTED.value
    rejected.model_output = {"semantic_match": {"similarity": 0.76}}
    pending = _candidate(uuid4(), community, topic)
    pending.status = EngagementCandidateStatus.NEEDS_REVIEW.value
    pending.prompt_render_summary = {"semantic_match": {"similarity": 0.65}}
    non_semantic = _candidate(uuid4(), community, topic)
    non_semantic.model_output = {}
    db = FakeDb(candidates=[approved, rejected, pending, non_semantic])

    response = await get_engagement_semantic_rollout(
        db,  # type: ignore[arg-type]
        window_days=14,
        community_id=None,
        topic_id=None,
    )

    assert response.total_semantic_candidates == 3
    assert response.reviewed_semantic_candidates == 2
    assert response.approved == 1
    assert response.rejected == 1
    assert response.pending == 1
    assert response.approval_rate == 0.5
    bands = {band.label: band for band in response.bands}
    assert bands["0.80-0.89"].approved == 1
    assert bands["0.70-0.79"].rejected == 1
    assert bands["0.62-0.69"].pending == 1


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
async def test_edit_engagement_candidate_creates_final_reply_revision() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    db = FakeDb(scalar_result=candidate)

    response = await post_engagement_candidate_edit(
        candidate.id,
        EngagementCandidateEditRequest(
            final_reply="Compare data ownership and export access before choosing.",
            edited_by="telegram:123",
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.final_reply == "Compare data ownership and export access before choosing."
    assert response.status == EngagementCandidateStatus.NEEDS_REVIEW.value
    assert db.commits == 1
    assert len(db.added) == 1
    assert db.added[0].revision_number == 1
    assert db.added[0].edited_by == "telegram:123"


@pytest.mark.asyncio
async def test_get_candidate_detail_returns_one_candidate() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    db = FakeDb(scalar_result=candidate)

    response = await get_engagement_candidate_detail(candidate.id, db)  # type: ignore[arg-type]

    assert response.id == candidate.id
    assert response.community_title == "Founder Circle"
    assert response.topic_name == "Open-source CRM"
    assert response.source_message_date == _now() - timedelta(minutes=30)
    assert response.detected_at == _now() - timedelta(minutes=25)
    assert response.moment_strength == "good"
    assert response.timeliness == "fresh"
    assert response.reply_value == "practical_tip"
    assert response.review_deadline_at == _now() + timedelta(minutes=30)
    assert response.reply_deadline_at == _now() + timedelta(minutes=60)


@pytest.mark.asyncio
async def test_candidate_revisions_route_returns_revision_history() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    revision = EngagementCandidateRevision(
        id=uuid4(),
        candidate_id=candidate.id,
        revision_number=2,
        reply_text="Edited final reply.",
        edited_by="telegram:123",
        edit_reason="manual edit",
        created_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
    )
    db = FakeDb(scalar_result=candidate, revisions=[revision])

    response = await get_engagement_candidate_revisions(candidate.id, db)  # type: ignore[arg-type]

    assert response.total == 1
    assert response.items[0].revision_number == 2
    assert response.items[0].reply_text == "Edited final reply."


@pytest.mark.asyncio
async def test_approve_engagement_candidate_uses_edited_final_reply() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    candidate.final_reply = "Edited final reply."
    db = FakeDb(scalar_result=candidate)

    response = await post_engagement_candidate_approve(
        candidate.id,
        EngagementCandidateApproveRequest(reviewed_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.status == EngagementCandidateStatus.APPROVED.value
    assert response.final_reply == "Edited final reply."


@pytest.mark.asyncio
async def test_expire_engagement_candidate_moves_review_candidate_to_expired() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    db = FakeDb(scalar_result=candidate)

    response = await post_engagement_candidate_expire(
        candidate.id,
        EngagementCandidateExpireRequest(expired_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.status == EngagementCandidateStatus.EXPIRED.value
    assert db.commits == 1


@pytest.mark.asyncio
async def test_retry_engagement_candidate_reopens_failed_candidate() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    candidate.status = EngagementCandidateStatus.FAILED.value
    candidate.reviewed_by = "telegram:123"
    candidate.reviewed_at = datetime(2026, 4, 20, tzinfo=timezone.utc)
    db = FakeDb(scalar_result=candidate)

    response = await post_engagement_candidate_retry(
        candidate.id,
        EngagementCandidateRetryRequest(retried_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.status == EngagementCandidateStatus.NEEDS_REVIEW.value
    assert response.reviewed_by is None
    assert response.reviewed_at is None
    assert db.commits == 1


@pytest.mark.asyncio
async def test_retry_engagement_candidate_rejects_non_failed_candidate() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    db = FakeDb(scalar_result=candidate)

    with pytest.raises(HTTPException) as exc_info:
        await post_engagement_candidate_retry(
            candidate.id,
            EngagementCandidateRetryRequest(retried_by="telegram:123"),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "candidate_not_retryable"
    assert db.commits == 0


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
async def test_approve_engagement_candidate_rejects_stale_candidate() -> None:
    community = _community(uuid4(), title="Founder Circle")
    topic = _topic(uuid4(), name="Open-source CRM")
    candidate = _candidate(uuid4(), community, topic)
    candidate.reply_deadline_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    db = FakeDb(scalar_result=candidate)

    with pytest.raises(HTTPException) as exc_info:
        await post_engagement_candidate_approve(
            candidate.id,
            EngagementCandidateApproveRequest(reviewed_by="telegram:123"),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "candidate_stale"
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
