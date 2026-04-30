from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.db.enums import (
    CommunityAccountMembershipStatus,
    CommunityStatus,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementOpportunityKind,
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
    EngagementSettings,
    EngagementStyleRule,
    EngagementTarget,
    EngagementTopic,
    TelegramAccount,
)

_FIXTURE_NOW = datetime.now(timezone.utc).replace(microsecond=0)


class FakeDb:
    def __init__(
        self,
        *,
        community: Community | None = None,
        settings: CommunityEngagementSettings | None = None,
        engagement: Engagement | None = None,
        engagement_settings: EngagementSettings | None = None,
        membership: CommunityAccountMembership | None = None,
        topic: EngagementTopic | None = None,
        style_rule: EngagementStyleRule | None = None,
        target: EngagementTarget | None = None,
        candidate: EngagementCandidate | None = None,
        candidates: list[EngagementCandidate] | None = None,
        revisions: list[EngagementCandidateRevision] | None = None,
        actions: list[EngagementAction] | None = None,
        account: TelegramAccount | None = None,
        scalar_result: object | None = None,
    ) -> None:
        self.community = community
        self.settings = settings
        self.engagement = engagement
        self.engagement_settings = engagement_settings
        self.membership = membership
        self.topic = topic
        self.style_rule = style_rule
        self.target = target
        self.candidate = candidate
        self.candidates = candidates
        self.revisions = revisions
        self.actions = actions
        self.account = account
        self.scalar_result = scalar_result
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0

    async def get(self, model: object, item_id: object) -> object | None:
        del item_id
        if model is Community:
            return self.community
        if model is Engagement:
            return self.engagement
        if model is EngagementSettings:
            return self.engagement_settings
        if model is CommunityAccountMembership:
            return self.membership
        if model is EngagementTopic:
            return self.topic
        if model is EngagementStyleRule:
            return self.style_rule
        if model is EngagementTarget:
            return self.target
        if model is EngagementCandidate:
            return self.candidate
        if model is TelegramAccount:
            return self.account
        return None

    async def scalar(self, statement: object) -> object | None:
        if self.scalar_result is not None:
            return self.scalar_result
        model_name = _selected_model_name(statement)
        if _is_count_query(statement):
            if model_name == "EngagementCandidate" or self.candidates is not None:
                return len(self.candidates or [])
            if model_name == "EngagementAction" or self.actions is not None:
                return len(self.actions or [])
        if model_name == "Engagement":
            return self.engagement
        if model_name == "EngagementSettings":
            return self.engagement_settings
        if model_name == "CommunityAccountMembership":
            return self.membership
        if model_name == "EngagementCandidate":
            return self.candidate
        if model_name == "EngagementAction":
            return self.actions[0] if self.actions else None
        if self.target is not None:
            return self.target
        if self.candidates is not None:
            return len(self.candidates)
        if self.actions is not None:
            return len(self.actions)
        return self.settings

    async def scalars(self, statement: object) -> list[object]:
        del statement
        if self.revisions is not None:
            return list(self.revisions)
        if self.actions is not None:
            return list(self.actions)
        return list(self.candidates or [])

    def add(self, model: object) -> None:
        self.added.append(model)
        if isinstance(model, EngagementAction):
            if self.actions is None:
                self.actions = []
            self.actions.append(model)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


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
) -> Engagement:
    return Engagement(
        id=uuid4(),
        target_id=target.id,
        community_id=target.community_id,
        topic_id=None if topic is None else topic.id,
        status=status,
        name=None,
        created_by="telegram:123",
        created_at=_now(),
        updated_at=_now(),
    )


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


def _is_count_query(statement: object) -> bool:
    descriptions = getattr(statement, "column_descriptions", None) or []
    return any(description.get("name") == "count" for description in descriptions)


def _candidate(
    candidate_id: object,
    community: Community,
    topic: EngagementTopic,
    *,
    expires_at: datetime | None = None,
) -> EngagementCandidate:
    candidate = EngagementCandidate(
        id=candidate_id,
        community_id=community.id,
        topic_id=topic.id,
        source_tg_message_id=123,
        source_excerpt="The group is comparing CRM tools.",
        source_message_date=_now() - timedelta(minutes=30),
        detected_at=_now() - timedelta(minutes=25),
        detected_reason="The group is comparing CRM alternatives.",
        moment_strength="good",
        timeliness="fresh",
        reply_value="practical_tip",
        opportunity_kind=EngagementOpportunityKind.ROOT.value,
        suggested_reply="Compare data ownership, integrations, and exit paths first.",
        risk_notes=[],
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        review_deadline_at=_now() + timedelta(minutes=30),
        reply_deadline_at=_now() + timedelta(minutes=60),
        expires_at=expires_at or datetime(2999, 4, 20, tzinfo=timezone.utc),
        created_at=_now(),
        updated_at=_now(),
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


def _now() -> datetime:
    return _FIXTURE_NOW
