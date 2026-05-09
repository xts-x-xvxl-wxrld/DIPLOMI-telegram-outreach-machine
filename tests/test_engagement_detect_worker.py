from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
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
    CollectionRun,
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementAction,
    EngagementCandidate,
    EngagementDraftUpdateRequest,
    EngagementTarget,
    EngagementTopic,
    Message,
)
from backend.services.community_engagement import create_engagement_candidate
from backend.services.engagement_embeddings import SemanticTriggerMatch
from backend.workers.engagement_detect import (
    CommunityContext,
    DetectionMessage,
    EngagementDetectionDecision,
    process_engagement_detect,
)
_FIXTURE_NOW = datetime.now(timezone.utc).replace(microsecond=0)

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
                    message_date=_now() - timedelta(minutes=30),
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
                    message_date=_now() - timedelta(minutes=30),
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
                    message_date=_now() - timedelta(minutes=30),
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
                    message_date=_now() - timedelta(minutes=30),
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
        message_date=_now() - timedelta(minutes=30),
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
                    message_date=_now() - timedelta(minutes=30),
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
                    message_date=_now() - timedelta(minutes=30),
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
        message_date=_now() - timedelta(minutes=30),
        is_replyable=True,
    )
    second = DetectionMessage(
        tg_message_id=102,
        text="CRM migration plan B",
        message_date=_now() - timedelta(minutes=29),
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
        source_message_date=_now() - timedelta(minutes=30),
        detected_at=_now() - timedelta(minutes=25),
        detected_reason="Existing candidate",
        moment_strength="good",
        timeliness="fresh",
        reply_value="other",
        suggested_reply="Existing reply",
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        risk_notes=[],
        review_deadline_at=_now() + timedelta(minutes=30),
        reply_deadline_at=_now() + timedelta(minutes=60),
        expires_at=_now() + timedelta(days=1),
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
                    message_date=_now() - timedelta(minutes=30),
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


@pytest.mark.asyncio
async def test_engagement_detect_skips_stale_candidate_for_automatic_runs() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["crm"])
    session = FakeSession(community=_community(community_id), settings=_settings(community_id))

    async def detector(_model_input: dict[str, object]) -> EngagementDetectionDecision:
        return EngagementDetectionDecision(
            should_engage=True,
            topic_match="CRM",
            source_tg_message_id=123,
            reason="The group is comparing CRM tools.",
            suggested_reply="Compare export access and integrations first.",
            risk_notes=[],
        )

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 180, "requested_by": None},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([topic]),
        sample_loader=lambda *_args, **_kwargs: _async_result(
            [
                DetectionMessage(
                    tg_message_id=123,
                    text="We are comparing CRM options.",
                    message_date=_now() - timedelta(minutes=120),
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
            engagement_reply_deadline_minutes=90,
        ),  # type: ignore[arg-type]
    )

    assert result["candidates_created"] == 0
    assert result["skipped_stale"] == 1
    assert session.candidates == []


@pytest.mark.asyncio
async def test_engagement_detect_rejects_person_level_reply_value_labels() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["crm"])
    session = FakeSession(community=_community(community_id), settings=_settings(community_id))

    async def detector(_model_input: dict[str, object]) -> dict[str, object]:
        return {
            "should_engage": True,
            "topic_match": "CRM",
            "source_tg_message_id": 123,
            "reason": "The group is comparing CRM tools.",
            "reply_value": "high_intent_buyer",
            "suggested_reply": "Compare data ownership and export access first.",
            "risk_notes": [],
        }

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
                    message_date=_now() - timedelta(minutes=30),
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
            engagement_reply_deadline_minutes=90,
        ),  # type: ignore[arg-type]
    )

    assert result["candidates_created"] == 0
    assert result["skipped_validation"] == 1
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
        topic: EngagementTopic | None = None,
        draft_update_requests: list[EngagementDraftUpdateRequest] | None = None,
        sent_actions: list[EngagementAction] | None = None,
    ) -> None:
        self.community = community
        self.settings = settings
        self.target = _target(community.id) if target is True else target
        self.existing_candidate = existing_candidate
        self.membership = _membership(community.id) if membership is True else membership
        self.topic = topic
        self.draft_update_requests = list(draft_update_requests or [])
        self.sent_actions = list(sent_actions or [])
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
        if model is EngagementCandidate:
            if self.existing_candidate is not None and self.existing_candidate.id == item_id:
                return self.existing_candidate
            return self.get_candidate(item_id)
        if model is EngagementDraftUpdateRequest:
            for request in self.draft_update_requests:
                if request.id == item_id:
                    return request
            return None
        if model is EngagementTopic and self.topic is not None and self.topic.id == item_id:
            return self.topic
        return None

    async def scalar(self, statement: object) -> object | None:
        entity = statement.column_descriptions[0]["entity"]  # type: ignore[attr-defined]
        if entity is CommunityEngagementSettings:
            return self.settings
        if entity is EngagementTarget:
            return self.target
        if entity is CommunityAccountMembership:
            return self.membership
        if entity is EngagementDraftUpdateRequest:
            compiled = statement.compile()
            for value in compiled.params.values():
                if hasattr(value, "hex"):
                    for request in self.draft_update_requests:
                        if request.source_candidate_id == value:
                            return request
            return self.draft_update_requests[0] if self.draft_update_requests else None
        if entity is EngagementCandidate:
            candidates = [
                candidate
                for candidate in [self.existing_candidate, *self.candidates]
                if isinstance(candidate, EngagementCandidate)
            ]
            if not candidates:
                return None
            compiled = statement.compile()
            ignored_ids = {
                item
                for value in compiled.params.values()
                if isinstance(value, (list, tuple, set))
                for item in value
                if hasattr(item, "hex")
            }
            sql = str(compiled)
            if "JOIN engagement_actions" in sql:
                return _match_candidate_from_sent_actions(
                    candidates=candidates,
                    sent_actions=self.sent_actions,
                    params=compiled.params,
                )
            for candidate in candidates:
                if candidate.id not in ignored_ids:
                    if _candidate_matches_statement(candidate, sql=sql, params=compiled.params):
                        return candidate
            return None
        if entity is EngagementTopic:
            return self.topic
        return None

    async def scalars(self, statement: object) -> object:
        entity = statement.column_descriptions[0]["entity"]  # type: ignore[attr-defined]
        if entity is EngagementAction:
            return _FakeScalarResult(self.sent_actions)
        if entity is EngagementDraftUpdateRequest:
            compiled = statement.compile()
            scoped_requests = list(self.draft_update_requests)
            for value in compiled.params.values():
                if hasattr(value, "hex"):
                    scoped_requests = [
                        request for request in scoped_requests if request.engagement_id == value
                    ]
                    break
            return _FakeScalarResult(scoped_requests)
        return _FakeScalarResult([])

    def add(self, model: object) -> None:
        if isinstance(model, EngagementCandidate):
            self.candidates.append(model)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    def get_candidate(self, candidate_id: object) -> EngagementCandidate | None:
        if self.existing_candidate is not None and self.existing_candidate.id == candidate_id:
            return self.existing_candidate
        for candidate in self.candidates:
            if candidate.id == candidate_id:
                return candidate
        return None


class _FakeScalarResult:
    def __init__(self, values: list[object]) -> None:
        self._values = list(values)

    def all(self) -> list[object]:
        return list(self._values)

    def __iter__(self):
        return iter(self._values)


class DetectionSampleSession:
    def __init__(
        self,
        *,
        runs: dict[object, CollectionRun] | None = None,
        stored_messages: list[Message] | None = None,
        artifact_runs: list[CollectionRun] | None = None,
    ) -> None:
        self.runs = runs or {}
        self.stored_messages = stored_messages or []
        self.artifact_runs = artifact_runs or []

    async def get(self, model: object, item_id: object) -> object | None:
        if model is CollectionRun:
            return self.runs.get(item_id)
        return None

    async def scalars(self, statement: object) -> list[object]:
        entity = statement.column_descriptions[0]["entity"]  # type: ignore[attr-defined]
        if entity is Message:
            return self.stored_messages
        if entity is CollectionRun:
            return self.artifact_runs
        return []


async def _async_result(value: object) -> object:
    return value


def _match_candidate_from_sent_actions(
    *,
    candidates: list[EngagementCandidate],
    sent_actions: list[EngagementAction],
    params: dict[str, object],
) -> EngagementCandidate | None:
    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    for action in sent_actions:
        if params.get("community_id_1") not in {None, action.community_id}:
            continue
        if params.get("telegram_account_id_1") not in {None, action.telegram_account_id}:
            continue
        if params.get("status_1") not in {None, action.status}:
            continue
        if params.get("sent_tg_message_id_1") not in {None, action.sent_tg_message_id}:
            continue
        candidate = candidate_by_id.get(action.candidate_id)
        if candidate is not None:
            return candidate
    return None


def _candidate_matches_statement(
    candidate: EngagementCandidate,
    *,
    sql: str,
    params: dict[str, object],
) -> bool:
    if "engagement_candidates.id =" in sql and params.get("id_1") not in {None, candidate.id}:
        return False
    if (
        "engagement_candidates.community_id =" in sql
        and params.get("community_id_1") not in {None, candidate.community_id}
    ):
        return False
    if "engagement_candidates.topic_id =" in sql and params.get("topic_id_1") not in {None, candidate.topic_id}:
        return False
    if (
        "engagement_candidates.source_tg_message_id =" in sql
        and params.get("source_tg_message_id_1") not in {None, candidate.source_tg_message_id}
    ):
        return False
    if (
        "engagement_candidates.source_excerpt =" in sql
        and params.get("source_excerpt_1") not in {None, candidate.source_excerpt}
    ):
        return False
    return True


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
        created_at=_now(),
        updated_at=_now(),
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
        joined_at=_now() - timedelta(hours=3),
    )


def _now() -> datetime:
    return _FIXTURE_NOW
