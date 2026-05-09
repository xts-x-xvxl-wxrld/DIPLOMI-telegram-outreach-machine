from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.db.enums import (
    CommunityStatus,
    EngagementActionStatus,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementOpportunityKind,
    EngagementTargetStatus,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementAction,
    EngagementCandidate,
    EngagementTarget,
    EngagementTopic,
)
from backend.services.community_engagement import create_engagement_candidate
from backend.workers.engagement_detect import (
    CommunityContext,
    DetectionMessage,
    EngagementDetectionDecision,
    process_engagement_detect,
)

_FIXTURE_NOW = datetime.now(timezone.utc).replace(microsecond=0)


@pytest.mark.asyncio
async def test_engagement_detect_creates_direct_reply_continuation_without_trigger_keywords() -> None:
    community_id = uuid4()
    topic = _topic(trigger_keywords=["crm"])
    membership = _membership(community_id)
    captured_inputs: list[dict[str, object]] = []
    previous_candidate = EngagementCandidate(
        id=uuid4(),
        community_id=community_id,
        topic_id=topic.id,
        source_tg_message_id=321,
        source_excerpt="Hey, I saw your question! I had a similar need and found @mosdxx super helpful for B2B AI sales automation.",
        source_message_date=_now() - timedelta(minutes=10),
        detected_at=_now() - timedelta(minutes=9),
        detected_reason="Existing sent reply.",
        moment_strength="good",
        timeliness="fresh",
        reply_value="practical_tip",
        suggested_reply="Hey, I saw your question! I had a similar need and found @mosdxx super helpful for B2B AI sales automation.",
        final_reply="Hey, I saw your question! I had a similar need and found @mosdxx super helpful for B2B AI sales automation.",
        status=EngagementCandidateStatus.SENT.value,
        reviewed_by="op",
        reviewed_at=_now() - timedelta(minutes=9),
        risk_notes=[],
        review_deadline_at=_now() + timedelta(minutes=20),
        reply_deadline_at=_now() + timedelta(minutes=50),
        expires_at=_now() + timedelta(days=1),
        created_at=_now() - timedelta(minutes=9),
        updated_at=_now() - timedelta(minutes=9),
    )
    session = FakeSession(
        community=_community(community_id),
        settings=_settings(community_id),
        membership=membership,
        existing_candidate=previous_candidate,
        sent_actions=[
            EngagementAction(
                id=uuid4(),
                candidate_id=previous_candidate.id,
                community_id=community_id,
                telegram_account_id=membership.telegram_account_id,
                action_type="reply",
                status=EngagementActionStatus.SENT.value,
                idempotency_key=f"engagement.send:{previous_candidate.id}",
                outbound_text=previous_candidate.final_reply,
                reply_to_tg_message_id=previous_candidate.source_tg_message_id,
                sent_tg_message_id=777,
                sent_at=_now() - timedelta(minutes=8),
                created_at=_now() - timedelta(minutes=8),
                updated_at=_now() - timedelta(minutes=8),
            )
        ],
    )

    async def detector(model_input: dict[str, object]) -> EngagementDetectionDecision:
        captured_inputs.append(model_input)
        assert model_input["source_post"]["tg_message_id"] == 888
        return EngagementDetectionDecision(
            should_engage=True,
            topic_match="CRM",
            source_tg_message_id=888,
            reason="They directly asked for more detail after the approved reply.",
            continuation_goal="provide_example",
            answered_question="What was the case?",
            avoid_repeating=["Do not restate the full original recommendation."],
            suggested_reply="The biggest difference for us was how much manual follow-up and lead routing it saved once the basics were set up.",
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
                    tg_message_id=888,
                    text="oh yeah? What was the case? can you tell me more about it?",
                    message_date=_now() - timedelta(minutes=2),
                    reply_to_tg_message_id=777,
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

    assert result["candidates_created"] == 1
    assert result["detector_calls"] == 1
    assert len(session.candidates) == 1
    candidate = session.candidates[0]
    assert candidate.source_tg_message_id == 888
    assert candidate.source_reply_to_tg_message_id == 777
    assert candidate.opportunity_kind == EngagementOpportunityKind.CONTINUATION.value
    assert candidate.root_candidate_id == previous_candidate.id
    assert candidate.model_output["continuation_goal"] == "provide_example"
    assert candidate.model_output["answered_question"] == "What was the case?"
    assert candidate.model_output["avoid_repeating"] == [
        "Do not restate the full original recommendation."
    ]
    prompt_runtime = captured_inputs[0]["_prompt_runtime"]
    assert "Continuation mode:" in prompt_runtime["system_prompt"]
    assert "Continuation task:" in prompt_runtime["rendered_user_prompt"]
    assert "Previous managed reply:" in prompt_runtime["rendered_user_prompt"]
    assert (
        "The biggest difference for us was how much manual follow-up and lead routing it saved once the basics were set up."
        not in prompt_runtime["rendered_user_prompt"]
    )
    assert captured_inputs[0]["thread"]["stage"] == "provide_example"
    assert captured_inputs[0]["thread"]["last_managed_reply"] == previous_candidate.final_reply


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
                    message_date=_now() - timedelta(minutes=30),
                    reply_to_tg_message_id=99,
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
    assert candidate.source_reply_to_tg_message_id == 99
    assert candidate.opportunity_kind == "root"
    assert candidate.root_candidate_id is None
    assert "[phone redacted]" in (candidate.source_excerpt or "")
    assert "+1 555" not in (candidate.source_excerpt or "")
    assert candidate.source_message_date == _now() - timedelta(minutes=30)
    assert candidate.detected_at >= candidate.source_message_date
    assert candidate.moment_strength == "good"
    assert candidate.timeliness == "fresh"
    assert candidate.reply_value == "other"
    assert candidate.review_deadline_at == _now() + timedelta(minutes=30)
    assert candidate.reply_deadline_at == _now() + timedelta(minutes=60)
    assert candidate.suggested_reply is not None
    assert candidate.model == "test-model"
    prompt_runtime = captured_inputs[0]["_prompt_runtime"]
    assert "Continuation mode:" not in prompt_runtime["system_prompt"]
    assert "Continuation task:" not in prompt_runtime["rendered_user_prompt"]
    assert "source_post" in captured_inputs[0]
    assert captured_inputs[0]["source_post"]["tg_message_id"] == 123
    assert captured_inputs[0]["source_post"]["reply_to_tg_message_id"] == 99
    assert captured_inputs[0]["messages"] == [captured_inputs[0]["source_post"]]
    assert "sender" not in str(captured_inputs[0]).casefold()
    assert "user_id" not in str(captured_inputs[0]).casefold()


class FakeSession:
    def __init__(
        self,
        *,
        community: Community,
        settings: CommunityEngagementSettings,
        target: EngagementTarget | None | bool = True,
        existing_candidate: EngagementCandidate | None = None,
        membership: CommunityAccountMembership | None | bool = True,
        sent_actions: list[EngagementAction] | None = None,
    ) -> None:
        self.community = community
        self.settings = settings
        self.target = _target(community.id) if target is True else target
        self.existing_candidate = existing_candidate
        self.membership = _membership(community.id) if membership is True else membership
        self.sent_actions = list(sent_actions or [])
        self.candidates: list[EngagementCandidate] = []
        self.commits = 0

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
            candidates = [
                candidate
                for candidate in [self.existing_candidate, *self.candidates]
                if isinstance(candidate, EngagementCandidate)
            ]
            if not candidates:
                return None
            compiled = statement.compile()
            sql = str(compiled)
            if "JOIN engagement_actions" in sql:
                return _match_candidate_from_sent_actions(
                    candidates=candidates,
                    sent_actions=self.sent_actions,
                    params=compiled.params,
                )
            for candidate in candidates:
                if _candidate_matches_statement(candidate, sql=sql, params=compiled.params):
                    return candidate
            return None
        return None

    async def scalars(self, statement: object) -> object:
        entity = statement.column_descriptions[0]["entity"]  # type: ignore[attr-defined]
        if entity is EngagementAction:
            return _FakeScalarResult(self.sent_actions)
        return _FakeScalarResult([])

    def add(self, model: object) -> None:
        if isinstance(model, EngagementCandidate):
            self.candidates.append(model)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class _FakeScalarResult:
    def __init__(self, values: list[object]) -> None:
        self._values = list(values)

    def __iter__(self):
        return iter(self._values)


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
