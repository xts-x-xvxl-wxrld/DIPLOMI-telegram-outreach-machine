from __future__ import annotations

import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.db.enums import (
    CommunityStatus,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementTargetStatus,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementCandidate,
    EngagementTarget,
    EngagementTopic,
)
from backend.services.community_engagement import create_engagement_candidate
from backend.services.engagement_embeddings import SemanticTriggerMatch
from backend.workers.engagement_detect import (
    CommunityContext,
    DetectionMessage,
    EngagementDetectionDecision,
    process_engagement_detect,
)


@pytest.mark.asyncio
async def test_engagement_detect_skips_model_when_keyword_prefilter_has_no_signal() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["crm"])
    session = FakeSession(community=_community(community_id), settings=_settings(community_id))

    async def detector(_model_input: dict[str, object]) -> EngagementDetectionDecision:
        raise AssertionError("detector should not run without keyword signal")

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 60, "requested_by": None},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([topic]),
        sample_loader=lambda *_args, **_kwargs: _async_result(
            [
                DetectionMessage(
                    tg_message_id=10,
                    text="Does anyone have newsletter tooling recommendations?",
                    message_date=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
                    is_replyable=True,
                )
            ]
        ),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=False,
        ),  # type: ignore[arg-type]
    )

    assert result["status"] == "processed"
    assert result["detector_calls"] == 0
    assert result["candidates_created"] == 0
    assert result["skipped_no_signal"] == 1
    assert session.candidates == []
    assert session.commits == 1


@pytest.mark.asyncio
async def test_engagement_detect_creates_candidate_without_sender_identity() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["crm"])
    session = FakeSession(community=_community(community_id), settings=_settings(community_id))
    captured_inputs: list[dict[str, object]] = []

    async def detector(model_input: dict[str, object]) -> EngagementDetectionDecision:
        captured_inputs.append(model_input)
        return EngagementDetectionDecision(
            should_engage=True,
            topic_match="CRM",
            source_tg_message_id=123,
            reason="The group is comparing CRM tools.",
            suggested_reply="A useful way to compare CRMs is to check data ownership, integrations, and how easy it is to leave later.",
            risk_notes=[],
        )

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 60, "requested_by": "op"},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([topic]),
        sample_loader=lambda *_args, **_kwargs: _async_result(
            [
                DetectionMessage(
                    tg_message_id=123,
                    text="We are comparing CRM options. Call me at +1 555 123 4567 if you know one.",
                    message_date=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
                    is_replyable=True,
                )
            ]
        ),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary="Community discusses SaaS operations.", dominant_themes=["ops"])
        ),
        candidate_creator=create_engagement_candidate,
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=False,
        ),  # type: ignore[arg-type]
    )

    assert result["candidates_created"] == 1
    assert result["detector_calls"] == 1
    assert len(session.candidates) == 1
    candidate = session.candidates[0]
    assert candidate.status == EngagementCandidateStatus.NEEDS_REVIEW.value
    assert candidate.source_tg_message_id == 123
    assert "[phone redacted]" in (candidate.source_excerpt or "")
    assert "+1 555" not in (candidate.source_excerpt or "")
    assert candidate.suggested_reply is not None
    assert candidate.model == "test-model"
    assert "source_post" in captured_inputs[0]
    assert captured_inputs[0]["source_post"]["tg_message_id"] == 123
    assert captured_inputs[0]["messages"] == [captured_inputs[0]["source_post"]]
    assert "sender" not in str(captured_inputs[0]).casefold()
    assert "user_id" not in str(captured_inputs[0]).casefold()


@pytest.mark.asyncio
async def test_engagement_detect_skips_without_approved_engagement_target() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["crm"])
    session = FakeSession(
        community=_community(community_id),
        settings=_settings(community_id),
        target=None,
    )

    async def detector(_model_input: dict[str, object]) -> EngagementDetectionDecision:
        raise AssertionError("detector should not run without approved engagement target")

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 60, "requested_by": None},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([topic]),
        sample_loader=lambda *_args, **_kwargs: _async_result(
            [
                DetectionMessage(
                    tg_message_id=123,
                    text="We are comparing CRM options.",
                    message_date=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
                    is_replyable=True,
                )
            ]
        ),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=False,
        ),  # type: ignore[arg-type]
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "engagement_target_detect_not_approved"
    assert session.candidates == []


@pytest.mark.asyncio
async def test_engagement_detect_skips_without_joined_membership() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["crm"])
    session = FakeSession(
        community=_community(community_id),
        settings=_settings(community_id),
        membership=None,
    )

    async def detector(_model_input: dict[str, object]) -> EngagementDetectionDecision:
        raise AssertionError("detector should not run without joined engagement membership")

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 60, "requested_by": None},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([topic]),
        sample_loader=lambda *_args, **_kwargs: _async_result(
            [
                DetectionMessage(
                    tg_message_id=123,
                    text="We are comparing CRM options.",
                    message_date=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
                    is_replyable=True,
                )
            ]
        ),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=False,
        ),  # type: ignore[arg-type]
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "no_joined_engagement_membership"


@pytest.mark.asyncio
async def test_engagement_detect_skips_semantic_only_topic_until_selector_is_enabled() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=[])
    topic.description = "People comparing CRM migration and evaluation tradeoffs."
    session = FakeSession(community=_community(community_id), settings=_settings(community_id))

    async def detector(_model_input: dict[str, object]) -> EngagementDetectionDecision:
        raise AssertionError("detector should not run for semantic-only topics before selector rollout")

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 60, "requested_by": None},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([topic]),
        sample_loader=lambda *_args, **_kwargs: _async_result(
            [
                DetectionMessage(
                    tg_message_id=123,
                    text="We are comparing CRM options.",
                    message_date=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
                    is_replyable=True,
                )
            ]
        ),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=False,
        ),  # type: ignore[arg-type]
    )

    assert result["status"] == "processed"
    assert result["detector_calls"] == 0
    assert result["skipped_no_signal"] == 1


@pytest.mark.asyncio
async def test_engagement_detect_uses_semantic_selector_when_enabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=[])
    topic.description = "People comparing CRM migration and evaluation tradeoffs."
    message = DetectionMessage(
        tg_message_id=123,
        text="We are weighing whether to migrate CRM data now or wait.",
        message_date=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        reply_context="Earlier thread asked about export access.",
        is_replyable=True,
    )
    session = FakeSession(community=_community(community_id), settings=_settings(community_id))
    captured_inputs: list[dict[str, object]] = []

    async def semantic_selector(*_args: object, **_kwargs: object) -> list[SemanticTriggerMatch]:
        return [
            SemanticTriggerMatch(
                message=message,
                similarity=0.7134567,
                threshold=0.62,
                rank=1,
                embedding_model="text-embedding-3-small",
                embedding_dimensions=512,
                source_text_hash="hash",
            )
        ]

    async def detector(model_input: dict[str, object]) -> EngagementDetectionDecision:
        captured_inputs.append(model_input)
        return EngagementDetectionDecision(
            should_engage=True,
            topic_match="CRM",
            source_tg_message_id=123,
            reason="The group is discussing CRM migration timing.",
            suggested_reply="One practical filter is whether export cleanup blocks other work; if it does, migrate in smaller chunks.",
            risk_notes=[],
        )

    with caplog.at_level(logging.INFO, logger="backend.workers.engagement_detect"):
        result = await process_engagement_detect(
            {"community_id": str(community_id), "window_minutes": 60, "requested_by": None},
            session_factory=lambda: session,
            detector=detector,
            active_topics_fn=lambda _session: _async_result([topic]),
            sample_loader=lambda *_args, **_kwargs: _async_result([message]),
            context_loader=lambda *_args, **_kwargs: _async_result(
                CommunityContext(latest_summary=None, dominant_themes=[])
            ),
            candidate_creator=create_engagement_candidate,
            semantic_selector=semantic_selector,
            settings=SimpleNamespace(
                openai_engagement_model="test-model",
                engagement_max_detector_calls_per_run=5,
                engagement_semantic_matching_enabled=True,
            ),  # type: ignore[arg-type]
        )

    assert result["candidates_created"] == 1
    assert result["detector_calls"] == 1
    assert result["semantic_matches_selected"] == 1
    assert result["semantic_candidates_created"] == 1
    assert captured_inputs[0]["source_post"]["tg_message_id"] == 123
    assert captured_inputs[0]["source_post"]["reply_context"] == "Earlier thread asked about export access."
    assert captured_inputs[0]["semantic_match"] == {
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 512,
        "similarity": 0.713457,
        "threshold": 0.62,
        "rank": 1,
    }
    assert session.candidates[0].model_output["semantic_match"] == {
        "model": "text-embedding-3-small",
        "dimensions": 512,
        "similarity": 0.713457,
        "threshold": 0.62,
        "rank": 1,
    }
    assert session.candidates[0].prompt_render_summary["semantic_match"] == {
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 512,
        "similarity": 0.713457,
        "threshold": 0.62,
        "rank": 1,
    }
    detect_logs = [record for record in caplog.records if record.message == "engagement.detect_summary"]
    assert detect_logs
    assert detect_logs[-1].engagement_detect["semantic_candidates_created"] == 1


@pytest.mark.asyncio
async def test_engagement_detect_skips_semantic_only_topic_when_selector_finds_no_match() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=[])
    topic.description = "People comparing CRM migration and evaluation tradeoffs."
    session = FakeSession(community=_community(community_id), settings=_settings(community_id))

    async def detector(_model_input: dict[str, object]) -> EngagementDetectionDecision:
        raise AssertionError("detector should not run when semantic selector finds no match")

    async def semantic_selector(*_args: object, **_kwargs: object) -> list[SemanticTriggerMatch]:
        return []

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 60, "requested_by": None},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([topic]),
        sample_loader=lambda *_args, **_kwargs: _async_result(
            [
                DetectionMessage(
                    tg_message_id=123,
                    text="We are comparing CRM options.",
                    message_date=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
                    is_replyable=True,
                )
            ]
        ),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        semantic_selector=semantic_selector,
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=True,
        ),  # type: ignore[arg-type]
    )

    assert result["status"] == "processed"
    assert result["detector_calls"] == 0
    assert result["skipped_no_signal"] == 1


@pytest.mark.asyncio
async def test_engagement_detect_keeps_keyword_fallback_when_semantic_has_no_match() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["crm"])
    session = FakeSession(community=_community(community_id), settings=_settings(community_id))

    async def detector(model_input: dict[str, object]) -> EngagementDetectionDecision:
        assert "semantic_match" not in model_input
        return EngagementDetectionDecision(
            should_engage=True,
            topic_match="CRM",
            source_tg_message_id=123,
            reason="The group is comparing CRM tools.",
            suggested_reply="Start with export access and integration needs before ranking tools.",
            risk_notes=[],
        )

    async def semantic_selector(*_args: object, **_kwargs: object) -> list[SemanticTriggerMatch]:
        return []

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 60, "requested_by": None},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([topic]),
        sample_loader=lambda *_args, **_kwargs: _async_result(
            [
                DetectionMessage(
                    tg_message_id=123,
                    text="We are comparing CRM options.",
                    message_date=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
                    is_replyable=True,
                )
            ]
        ),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        candidate_creator=create_engagement_candidate,
        semantic_selector=semantic_selector,
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=True,
        ),  # type: ignore[arg-type]
    )

    assert result["candidates_created"] == 1
    assert result["detector_calls"] == 1
    assert session.candidates[0].model_output.get("semantic_match") is None


@pytest.mark.asyncio
async def test_engagement_detect_caps_semantic_detector_calls_per_run() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=[])
    topic.description = "People comparing CRM migration and evaluation tradeoffs."
    first = DetectionMessage(
        tg_message_id=101,
        text="CRM migration plan A",
        message_date=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        is_replyable=True,
    )
    second = DetectionMessage(
        tg_message_id=102,
        text="CRM migration plan B",
        message_date=datetime(2026, 4, 19, 12, 1, tzinfo=timezone.utc),
        is_replyable=True,
    )
    session = FakeSession(community=_community(community_id), settings=_settings(community_id))
    called_message_ids: list[int | None] = []

    async def semantic_selector(*_args: object, **_kwargs: object) -> list[SemanticTriggerMatch]:
        return [
            SemanticTriggerMatch(
                message=first,
                similarity=0.9,
                threshold=0.62,
                rank=1,
                embedding_model="embed",
                embedding_dimensions=2,
                source_text_hash="first",
            ),
            SemanticTriggerMatch(
                message=second,
                similarity=0.8,
                threshold=0.62,
                rank=2,
                embedding_model="embed",
                embedding_dimensions=2,
                source_text_hash="second",
            ),
        ]

    async def detector(model_input: dict[str, object]) -> EngagementDetectionDecision:
        called_message_ids.append(model_input["source_post"]["tg_message_id"])
        return EngagementDetectionDecision(
            should_engage=False,
            topic_match=None,
            source_tg_message_id=model_input["source_post"]["tg_message_id"],
            reason="Weak moment.",
            suggested_reply=None,
            risk_notes=[],
        )

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 60, "requested_by": None},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([topic]),
        sample_loader=lambda *_args, **_kwargs: _async_result([first, second]),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        semantic_selector=semantic_selector,
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=1,
            engagement_semantic_matching_enabled=True,
        ),  # type: ignore[arg-type]
    )

    assert result["detector_calls"] == 1
    assert result["skipped_detector_cap"] == 1
    assert called_message_ids == [101]


@pytest.mark.asyncio
async def test_engagement_detect_skips_duplicate_active_candidate() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["crm"])
    existing = EngagementCandidate(
        id=uuid4(),
        community_id=community_id,
        topic_id=topic.id,
        source_tg_message_id=123,
        source_excerpt="We are comparing CRM options.",
        detected_reason="Existing candidate",
        suggested_reply="Existing reply",
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        risk_notes=[],
        expires_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )
    session = FakeSession(
        community=_community(community_id),
        settings=_settings(community_id),
        existing_candidate=existing,
    )

    async def detector(_model_input: dict[str, object]) -> EngagementDetectionDecision:
        return EngagementDetectionDecision(
            should_engage=True,
            topic_match="CRM",
            source_tg_message_id=123,
            reason="The group is comparing CRM tools.",
            suggested_reply="Compare data ownership and integrations first.",
            risk_notes=[],
        )

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 60, "requested_by": None},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([topic]),
        sample_loader=lambda *_args, **_kwargs: _async_result(
            [
                DetectionMessage(
                    tg_message_id=123,
                    text="We are comparing CRM options.",
                    message_date=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
                    is_replyable=True,
                )
            ]
        ),
        context_loader=lambda *_args, **_kwargs: _async_result(
            CommunityContext(latest_summary=None, dominant_themes=[])
        ),
        candidate_creator=create_engagement_candidate,
        settings=SimpleNamespace(
            openai_engagement_model="test-model",
            engagement_max_detector_calls_per_run=5,
            engagement_semantic_matching_enabled=False,
        ),  # type: ignore[arg-type]
    )

    assert result["candidates_created"] == 0
    assert result["skipped_dedupe"] == 1
    assert session.candidates == []


class FakeSession:
    def __init__(
        self,
        *,
        community: Community,
        settings: CommunityEngagementSettings,
        target: EngagementTarget | None | bool = True,
        existing_candidate: EngagementCandidate | None = None,
        membership: CommunityAccountMembership | None | bool = True,
    ) -> None:
        self.community = community
        self.settings = settings
        self.target = _target(community.id) if target is True else target
        self.existing_candidate = existing_candidate
        self.membership = _membership(community.id) if membership is True else membership
        self.candidates: list[EngagementCandidate] = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def get(self, model: object, item_id: object) -> object | None:
        if model is Community and item_id == self.community.id:
            return self.community
        return None

    async def scalar(self, statement: object) -> object | None:
        entity = statement.column_descriptions[0]["entity"]  # type: ignore[attr-defined]
        if entity is CommunityEngagementSettings:
            return self.settings
        if entity is EngagementTarget:
            return self.target
        if entity is CommunityAccountMembership:
            return self.membership
        if entity is EngagementCandidate:
            return self.existing_candidate
        return None

    def add(self, model: object) -> None:
        if isinstance(model, EngagementCandidate):
            self.candidates.append(model)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


async def _async_result(value: object) -> object:
    return value


def _community(community_id: object) -> Community:
    return Community(
        id=community_id,
        tg_id=100,
        username="example",
        title="Example Group",
        description="SaaS operators",
        is_group=True,
        status=CommunityStatus.MONITORING.value,
        store_messages=False,
    )


def _settings(community_id: object) -> CommunityEngagementSettings:
    return CommunityEngagementSettings(
        id=uuid4(),
        community_id=community_id,
        mode=EngagementMode.SUGGEST.value,
        allow_join=False,
        allow_post=False,
        reply_only=True,
        require_approval=True,
        max_posts_per_day=1,
        min_minutes_between_posts=240,
    )


def _topic(*, trigger_keywords: list[str]) -> EngagementTopic:
    return EngagementTopic(
        id=uuid4(),
        name="CRM",
        description="CRM discussion",
        stance_guidance="Be useful and non-salesy.",
        trigger_keywords=trigger_keywords,
        negative_keywords=[],
        example_good_replies=[],
        example_bad_replies=[],
        active=True,
        created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
    )


def _target(community_id: object) -> EngagementTarget:
    return EngagementTarget(
        id=uuid4(),
        community_id=community_id,
        submitted_ref=str(community_id),
        submitted_ref_type="community_id",
        status=EngagementTargetStatus.APPROVED.value,
        allow_join=True,
        allow_detect=True,
        allow_post=True,
        added_by="op",
    )


def _membership(community_id: object) -> CommunityAccountMembership:
    return CommunityAccountMembership(
        id=uuid4(),
        community_id=community_id,
        telegram_account_id=uuid4(),
        status="joined",
        joined_at=datetime(2026, 4, 19, 11, 0, tzinfo=timezone.utc),
    )
