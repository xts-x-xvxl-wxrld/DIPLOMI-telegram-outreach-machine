from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.db.enums import CommunityStatus, EngagementMode, EngagementTargetStatus
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
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
async def test_engagement_detect_allows_draft_creation_during_post_join_warmup() -> None:
    community_id = uuid4()
    membership = _membership(community_id)
    membership.joined_at = _now() - timedelta(minutes=30)
    session = FakeSession(
        community=_community(community_id),
        settings=_settings(community_id),
        membership=membership,
    )

    async def detector(model_input: dict[str, object]) -> EngagementDetectionDecision:
        assert model_input["source_post"]["tg_message_id"] == 123
        return EngagementDetectionDecision(
            should_engage=True,
            topic_match="tomatoes",
            source_tg_message_id=123,
            reason="The group is asking where to buy tomatoes.",
            suggested_reply="I usually compare a couple of neighborhood produce spots early in the day because the good tomatoes go first.",
            risk_notes=[],
        )

    result = await process_engagement_detect(
        {"community_id": str(community_id), "window_minutes": 60, "requested_by": "op"},
        session_factory=lambda: session,
        detector=detector,
        active_topics_fn=lambda _session: _async_result([_topic(trigger_keywords=["tomatoes"])]),
        sample_loader=lambda *_args, **_kwargs: _async_result(
            [
                DetectionMessage(
                    tg_message_id=123,
                    text="Does anyone know where to buy decent tomatoes nearby?",
                    message_date=_now() - timedelta(minutes=5),
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

    assert result["status"] == "processed"
    assert result["detector_calls"] == 1
    assert result["candidates_created"] == 1
    assert session.candidates[0].source_tg_message_id == 123


class FakeSession:
    def __init__(
        self,
        *,
        community: Community,
        settings: CommunityEngagementSettings,
        membership: CommunityAccountMembership,
    ) -> None:
        self.community = community
        self.settings = settings
        self.membership = membership
        self.target = _target(community.id)
        self.candidates: list[EngagementCandidate] = []

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
        return None

    def add(self, model: object) -> None:
        if isinstance(model, EngagementCandidate):
            self.candidates.append(model)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


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
        name="tomatoes",
        description="Tomato buying discussion",
        stance_guidance="Be useful and concise.",
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
