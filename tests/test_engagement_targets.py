from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from backend.db.enums import (
    CommunitySource,
    CommunityStatus,
    EngagementTargetRefType,
    EngagementTargetStatus,
    TelegramEntityType,
)
from backend.db.models import Community, EngagementTarget
from backend.services.community_engagement import (
    has_engagement_target_permission,
    resolve_engagement_target,
)
from backend.services.telegram_entity_intake import TelegramEntityInfo, TelegramEntityResolveOutcome


@pytest.mark.asyncio
async def test_resolve_engagement_target_saves_candidate_community_and_links_target() -> None:
    target = _target()
    db = FakeDb(target=target)
    resolver = FakeResolver(
        {
            "example": TelegramEntityResolveOutcome.resolved(
                TelegramEntityInfo(
                    entity_type=TelegramEntityType.GROUP,
                    tg_id=12345,
                    username="example",
                    title="Example Group",
                    description="Public operator group",
                    member_count=500,
                    is_group=True,
                    is_broadcast=False,
                )
            )
        }
    )

    summary = await resolve_engagement_target(db, target_id=target.id, resolver=resolver)  # type: ignore[arg-type]

    assert summary.status == EngagementTargetStatus.RESOLVED.value
    assert summary.community_id == db.communities[0].id
    assert target.community_id == db.communities[0].id
    assert db.communities[0].status == CommunityStatus.CANDIDATE.value
    assert db.communities[0].source == CommunitySource.MANUAL.value
    assert db.communities[0].match_reason == "Engagement target intake: username:example"
    assert db.seed_groups == []
    assert db.seed_channels == []


@pytest.mark.asyncio
async def test_resolve_engagement_target_fails_non_community_entity() -> None:
    target = _target()
    db = FakeDb(target=target)
    resolver = FakeResolver(
        {
            "example": TelegramEntityResolveOutcome.resolved(
                TelegramEntityInfo(
                    entity_type=TelegramEntityType.USER,
                    tg_id=12345,
                    username="example",
                    first_name="Example",
                )
            )
        }
    )

    summary = await resolve_engagement_target(db, target_id=target.id, resolver=resolver)  # type: ignore[arg-type]

    assert summary.status == EngagementTargetStatus.FAILED.value
    assert summary.error_message == "Resolved target is not a community"
    assert target.community_id is None
    assert db.communities == []


@pytest.mark.asyncio
async def test_engagement_target_permission_requires_approved_target_and_flag() -> None:
    community_id = uuid4()
    approved = _target(community_id=community_id, status=EngagementTargetStatus.APPROVED.value)
    approved.allow_join = True
    approved.allow_detect = False
    db = FakeDb(targets=[approved])

    assert await has_engagement_target_permission(  # type: ignore[arg-type]
        db,
        community_id=community_id,
        permission="join",
    )
    assert not await has_engagement_target_permission(  # type: ignore[arg-type]
        db,
        community_id=community_id,
        permission="detect",
    )

    approved.status = EngagementTargetStatus.RESOLVED.value
    assert not await has_engagement_target_permission(  # type: ignore[arg-type]
        db,
        community_id=community_id,
        permission="join",
    )


@pytest.mark.asyncio
async def test_engagement_target_permission_allows_any_approved_target_with_requested_flag() -> None:
    community_id = uuid4()
    approved_without_detect = _target(
        community_id=community_id,
        status=EngagementTargetStatus.APPROVED.value,
    )
    approved_without_detect.allow_detect = False
    approved_with_detect = _target(
        community_id=community_id,
        status=EngagementTargetStatus.APPROVED.value,
    )
    approved_with_detect.allow_detect = True
    db = FakeDb(targets=[approved_without_detect, approved_with_detect])

    assert await has_engagement_target_permission(  # type: ignore[arg-type]
        db,
        community_id=community_id,
        permission="detect",
    )


class FakeResolver:
    def __init__(self, outcomes: dict[str, TelegramEntityResolveOutcome]) -> None:
        self.outcomes = outcomes

    async def resolve_entity(self, username: str) -> TelegramEntityResolveOutcome:
        return self.outcomes[username]


class FakeDb:
    def __init__(
        self,
        *,
        target: EngagementTarget | None = None,
        targets: list[EngagementTarget] | None = None,
    ) -> None:
        self.target = target
        self.targets = list(targets or ([] if target is None else [target]))
        self.communities: list[Community] = []
        self.seed_groups: list[object] = []
        self.seed_channels: list[object] = []
        self.flushes = 0

    async def get(self, model: object, item_id: UUID) -> object | None:
        if model is EngagementTarget:
            for target in self.targets:
                if item_id == target.id:
                    return target
        return None

    async def scalar(self, statement: object) -> object | None:
        entity = statement.column_descriptions[0]["entity"]  # type: ignore[attr-defined]
        if entity is Community:
            return self.communities[0] if self.communities else None
        if entity is EngagementTarget:
            statement_text = str(statement)
            required_permission: str | None = None
            if "engagement_targets.allow_join IS true" in statement_text:
                required_permission = "allow_join"
            elif "engagement_targets.allow_detect IS true" in statement_text:
                required_permission = "allow_detect"
            elif "engagement_targets.allow_post IS true" in statement_text:
                required_permission = "allow_post"

            for target in self.targets:
                if target.status != EngagementTargetStatus.APPROVED.value:
                    continue
                if required_permission is not None and not getattr(target, required_permission):
                    continue
                return target
            return None
        return None

    def add(self, model: object) -> None:
        if isinstance(model, Community):
            self.communities.append(model)

    async def flush(self) -> None:
        self.flushes += 1


def _target(
    *,
    community_id: UUID | None = None,
    status: str = EngagementTargetStatus.PENDING.value,
) -> EngagementTarget:
    return EngagementTarget(
        id=uuid4(),
        community_id=community_id,
        submitted_ref="username:example" if community_id is None else str(community_id),
        submitted_ref_type=EngagementTargetRefType.TELEGRAM_USERNAME.value
        if community_id is None
        else EngagementTargetRefType.COMMUNITY_ID.value,
        status=status,
        allow_join=False,
        allow_detect=False,
        allow_post=False,
        added_by="telegram:123",
        created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
    )
