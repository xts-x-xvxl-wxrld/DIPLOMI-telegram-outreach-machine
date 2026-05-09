from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.db.enums import EngagementCandidateStatus
from backend.db.models import EngagementCandidate, EngagementDraftUpdateRequest
from backend.services.community_engagement import create_engagement_candidate
from backend.workers.engagement_detect import (
    CommunityContext,
    DetectionMessage,
    EngagementDetectionDecision,
    process_engagement_detect,
)
from tests.test_engagement_detect_worker import (
    FakeSession,
    _async_result,
    _community,
    _now,
    _settings,
    _topic,
)


@pytest.mark.asyncio
async def test_engagement_detect_completes_pending_draft_update_request() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["automation"])
    source_candidate = EngagementCandidate(
        id=uuid4(),
        community_id=community_id,
        topic_id=topic.id,
        source_tg_message_id=51,
        source_excerpt="Serious question: has anyone worked with a B2B AI sales automation agency?",
        source_message_date=_now() - timedelta(hours=3),
        detected_at=_now() - timedelta(hours=3),
        detected_reason="Original draft felt too promotional.",
        moment_strength="good",
        timeliness="stale",
        reply_value="other",
        suggested_reply="Hey! I had a similar need and found great help from @mosdxx.",
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        risk_notes=[],
        review_deadline_at=_now() - timedelta(hours=2, minutes=30),
        reply_deadline_at=_now() - timedelta(hours=2),
        expires_at=_now() + timedelta(days=1),
    )
    request = EngagementDraftUpdateRequest(
        id=uuid4(),
        engagement_id=uuid4(),
        source_candidate_id=source_candidate.id,
        replacement_candidate_id=None,
        status="pending",
        edit_request="This is too formal. Make it rougher.",
        requested_by="telegram:123",
        source_queue_created_at=source_candidate.created_at or _now(),
        created_at=_now(),
        updated_at=_now(),
        completed_at=None,
    )
    session = FakeSession(
        community=_community(community_id),
        settings=_settings(community_id),
        topic=topic,
        existing_candidate=source_candidate,
        draft_update_requests=[request],
    )
    captured_inputs: list[dict[str, object]] = []

    async def detector(model_input: dict[str, object]) -> EngagementDetectionDecision:
        captured_inputs.append(model_input)
        return EngagementDetectionDecision(
            should_engage=True,
            topic_match="B2B AI Sales Automation",
            source_tg_message_id=51,
            reason="The post is asking for practical evaluation criteria.",
            suggested_reply=(
                "Would probably pressure-test how they handle deliverability, personalization, "
                "and who owns the workflow once it is live."
            ),
            risk_notes=[],
        )

    async def sample_loader(*_args: object, **_kwargs: object) -> list[DetectionMessage]:
        raise AssertionError("rewrite jobs should not wait for recent collection samples")

    result = await process_engagement_detect(
        {
            "community_id": str(community_id),
            "draft_update_request_id": str(request.id),
            "window_minutes": 60,
            "requested_by": "telegram:123",
        },
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([]),
        sample_loader=sample_loader,
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        candidate_creator=create_engagement_candidate,
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=False,
            engagement_reply_deadline_minutes=90,
        ),  # type: ignore[arg-type]
    )

    assert result["candidates_created"] == 1
    assert result["detector_calls"] == 1
    assert request.status == "completed"
    assert request.replacement_candidate_id is not None
    assert session.flushes >= 2
    replacement = session.get_candidate(request.replacement_candidate_id)
    assert replacement is not None
    assert replacement.source_tg_message_id == 51
    prompt_runtime = captured_inputs[0]["_prompt_runtime"]
    assert (
        "Treat the normal topic, style, and safety guidance above as the base instructions for this rewrite."
        in prompt_runtime["rendered_user_prompt"]
    )
    assert "Operator edit request: This is too formal. Make it rougher." in prompt_runtime["rendered_user_prompt"]
    assert "Previous draft: Hey! I had a similar need and found great help from @mosdxx." in prompt_runtime["rendered_user_prompt"]
    assert (
        "Keep the previous draft's core recommendation, conversion goal, and concrete CTA unless the operator "
        "explicitly asked to change them or they conflict with the safety rules above."
        in prompt_runtime["rendered_user_prompt"]
    )


@pytest.mark.asyncio
async def test_engagement_detect_restores_source_draft_when_rewrite_cannot_be_generated() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["automation"])
    source_candidate = EngagementCandidate(
        id=uuid4(),
        community_id=community_id,
        topic_id=topic.id,
        source_tg_message_id=51,
        source_excerpt="Serious question: has anyone worked with a B2B AI sales automation agency?",
        source_message_date=_now() - timedelta(hours=3),
        detected_at=_now() - timedelta(hours=3),
        detected_reason="Original draft felt too promotional.",
        moment_strength="good",
        timeliness="stale",
        reply_value="other",
        suggested_reply="Hey! I had a similar need and found great help from @mosdxx.",
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        risk_notes=[],
        review_deadline_at=_now() - timedelta(hours=2, minutes=30),
        reply_deadline_at=_now() - timedelta(hours=2),
        expires_at=_now() + timedelta(days=1),
    )
    request = EngagementDraftUpdateRequest(
        id=uuid4(),
        engagement_id=uuid4(),
        source_candidate_id=source_candidate.id,
        replacement_candidate_id=None,
        status="pending",
        edit_request="This is too formal. Make it rougher.",
        requested_by="telegram:123",
        source_queue_created_at=source_candidate.created_at or _now(),
        created_at=_now(),
        updated_at=_now(),
        completed_at=None,
    )
    session = FakeSession(
        community=_community(community_id),
        settings=_settings(community_id),
        topic=topic,
        existing_candidate=source_candidate,
        draft_update_requests=[request],
    )

    async def detector(_model_input: dict[str, object]) -> EngagementDetectionDecision:
        return EngagementDetectionDecision(
            should_engage=False,
            topic_match=None,
            source_tg_message_id=51,
            reason="No better reply.",
            suggested_reply=None,
            risk_notes=[],
        )

    result = await process_engagement_detect(
        {
            "community_id": str(community_id),
            "draft_update_request_id": str(request.id),
            "window_minutes": 60,
            "requested_by": "telegram:123",
        },
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([]),
        sample_loader=lambda *_args, **_kwargs: _async_result([]),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        candidate_creator=create_engagement_candidate,
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=False,
            engagement_reply_deadline_minutes=90,
        ),  # type: ignore[arg-type]
    )

    assert result["candidates_created"] == 0
    assert result["skipped_no_signal"] == 1
    assert request.status == "failed"
    assert request.replacement_candidate_id is None
    assert session.candidates == []


@pytest.mark.asyncio
async def test_engagement_detect_creates_new_candidate_for_second_revision_loop() -> None:
    community_id = uuid4()
    engagement_id = uuid4()
    topic = _topic(trigger_keywords=["automation"])
    original_candidate = EngagementCandidate(
        id=uuid4(),
        community_id=community_id,
        topic_id=topic.id,
        source_tg_message_id=51,
        source_excerpt="Serious question: has anyone worked with a B2B AI sales automation agency?",
        source_message_date=_now() - timedelta(hours=3),
        detected_at=_now() - timedelta(hours=3),
        detected_reason="Original draft felt too promotional.",
        moment_strength="good",
        timeliness="stale",
        reply_value="other",
        suggested_reply="Hey! I had a similar need and found great help from @mosdxx.",
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        risk_notes=[],
        review_deadline_at=_now() - timedelta(hours=2, minutes=30),
        reply_deadline_at=_now() - timedelta(hours=2),
        expires_at=_now() + timedelta(days=1),
    )
    current_candidate = EngagementCandidate(
        id=uuid4(),
        community_id=community_id,
        topic_id=topic.id,
        source_tg_message_id=51,
        source_excerpt="Serious question: has anyone worked with a B2B AI sales automation agency?",
        source_message_date=_now() - timedelta(hours=3),
        detected_at=_now() - timedelta(hours=2),
        detected_reason="First rewrite recovery.",
        moment_strength="good",
        timeliness="stale",
        reply_value="other",
        suggested_reply="Would sanity-check deliverability, personalization, and workflow ownership first.",
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        risk_notes=[],
        review_deadline_at=_now() - timedelta(hours=1, minutes=30),
        reply_deadline_at=_now() - timedelta(hours=1),
        expires_at=_now() + timedelta(days=1),
    )
    first_request = EngagementDraftUpdateRequest(
        id=uuid4(),
        engagement_id=engagement_id,
        source_candidate_id=original_candidate.id,
        replacement_candidate_id=current_candidate.id,
        status="completed",
        edit_request="This is too formal. Make it rougher.",
        requested_by="telegram:123",
        source_queue_created_at=original_candidate.created_at or _now(),
        created_at=_now() - timedelta(minutes=10),
        updated_at=_now() - timedelta(minutes=10),
        completed_at=_now() - timedelta(minutes=10),
    )
    second_request = EngagementDraftUpdateRequest(
        id=uuid4(),
        engagement_id=engagement_id,
        source_candidate_id=current_candidate.id,
        replacement_candidate_id=None,
        status="pending",
        edit_request="yeah just be a bit more plain buddy",
        requested_by="telegram:123",
        source_queue_created_at=current_candidate.created_at or _now(),
        created_at=_now(),
        updated_at=_now(),
        completed_at=None,
    )
    session = FakeSession(
        community=_community(community_id),
        settings=_settings(community_id),
        topic=topic,
        existing_candidate=current_candidate,
        draft_update_requests=[first_request, second_request],
    )
    session.candidates.append(original_candidate)

    async def detector(_model_input: dict[str, object]) -> EngagementDetectionDecision:
        return EngagementDetectionDecision(
            should_engage=True,
            topic_match="B2B AI Sales Automation",
            source_tg_message_id=51,
            reason="The post is still relevant for a rewrite.",
            suggested_reply="Probably just keep it blunt and point them to @mosdxx without overselling it.",
            risk_notes=[],
        )

    result = await process_engagement_detect(
        {
            "community_id": str(community_id),
            "draft_update_request_id": str(second_request.id),
            "window_minutes": 60,
            "requested_by": "telegram:123",
        },
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([]),
        sample_loader=lambda *_args, **_kwargs: _async_result([]),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        candidate_creator=create_engagement_candidate,
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=False,
            engagement_reply_deadline_minutes=90,
        ),  # type: ignore[arg-type]
    )

    assert result["candidates_created"] == 1
    assert second_request.status == "completed"
    assert second_request.replacement_candidate_id is not None
    assert second_request.replacement_candidate_id not in {
        original_candidate.id,
        current_candidate.id,
    }
    replacement = session.get_candidate(second_request.replacement_candidate_id)
    assert replacement is not None
    assert replacement.suggested_reply == (
        "Probably just keep it blunt and point them to @mosdxx without overselling it."
    )
