from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.db.enums import CommunitySource, CommunityStatus, SeedChannelStatus
from backend.db.models import Community, SeedChannel, SeedGroup
from backend.services.seed_resolution import (
    TelegramCommunityInfo,
    TelegramResolveOutcome,
    TransientResolveError,
    resolve_seed_group,
)


@pytest.mark.asyncio
async def test_resolved_channel_creates_manual_candidate_community() -> None:
    seed_group = _seed_group()
    seed_channel = _seed_channel(seed_group.id, username="founders")
    repository = FakeSeedResolutionRepository(seed_group=seed_group, seeds=[seed_channel])
    resolver = FakeResolver(
        {
            "founders": TelegramResolveOutcome.resolved(
                TelegramCommunityInfo(
                    tg_id=12345,
                    username="founders",
                    title="Founder Circle",
                    description="Startup founder discussions",
                    member_count=1200,
                    is_group=True,
                    is_broadcast=False,
                )
            )
        }
    )

    summary = await resolve_seed_group(
        repository,
        seed_group_id=seed_group.id,
        limit=100,
        retry_failed=False,
        resolver=resolver,
    )

    assert summary.counts()[SeedChannelStatus.RESOLVED.value] == 1
    assert seed_channel.status == SeedChannelStatus.RESOLVED.value
    assert seed_channel.community_id == repository.communities[0].id
    community = repository.communities[0]
    assert community.status == CommunityStatus.CANDIDATE.value
    assert community.source == CommunitySource.MANUAL.value
    assert community.match_reason == "Imported manual seed: SaaS Seeds"
    assert community.member_count == 1200
    assert resolver.calls == ["founders"]


@pytest.mark.asyncio
async def test_resolved_existing_community_preserves_operator_status() -> None:
    seed_group = _seed_group()
    seed_channel = _seed_channel(seed_group.id, username="founders")
    existing = Community(
        id=uuid4(),
        tg_id=12345,
        username="old_founders",
        title="Old Title",
        status=CommunityStatus.REJECTED.value,
        source=CommunitySource.EXPANSION.value,
        store_messages=False,
    )
    repository = FakeSeedResolutionRepository(
        seed_group=seed_group,
        seeds=[seed_channel],
        communities=[existing],
    )
    resolver = FakeResolver(
        {
            "founders": TelegramResolveOutcome.resolved(
                TelegramCommunityInfo(
                    tg_id=12345,
                    username="founders",
                    title="Updated Title",
                    description=None,
                    member_count=None,
                    is_group=False,
                    is_broadcast=True,
                )
            )
        }
    )

    await resolve_seed_group(
        repository,
        seed_group_id=seed_group.id,
        limit=100,
        retry_failed=False,
        resolver=resolver,
    )

    assert seed_channel.status == SeedChannelStatus.RESOLVED.value
    assert seed_channel.community_id == existing.id
    assert existing.status == CommunityStatus.REJECTED.value
    assert existing.source == CommunitySource.MANUAL.value
    assert existing.username == "founders"
    assert existing.title == "Updated Title"
    assert len(repository.communities) == 1


@pytest.mark.asyncio
async def test_inaccessible_target_marks_seed_without_creating_community() -> None:
    seed_group = _seed_group()
    seed_channel = _seed_channel(seed_group.id, username="privateish")
    repository = FakeSeedResolutionRepository(seed_group=seed_group, seeds=[seed_channel])
    resolver = FakeResolver(
        {"privateish": TelegramResolveOutcome.inaccessible("Target is not accessible")}
    )

    summary = await resolve_seed_group(
        repository,
        seed_group_id=seed_group.id,
        limit=100,
        retry_failed=False,
        resolver=resolver,
    )

    assert summary.counts()[SeedChannelStatus.INACCESSIBLE.value] == 1
    assert seed_channel.status == SeedChannelStatus.INACCESSIBLE.value
    assert seed_channel.community_id is None
    assert repository.communities == []


@pytest.mark.asyncio
async def test_non_community_target_marks_seed_without_creating_community() -> None:
    seed_group = _seed_group()
    seed_channel = _seed_channel(seed_group.id, username="someuser")
    repository = FakeSeedResolutionRepository(seed_group=seed_group, seeds=[seed_channel])
    resolver = FakeResolver({"someuser": TelegramResolveOutcome.not_community("User or bot")})

    summary = await resolve_seed_group(
        repository,
        seed_group_id=seed_group.id,
        limit=100,
        retry_failed=False,
        resolver=resolver,
    )

    assert summary.counts()[SeedChannelStatus.NOT_COMMUNITY.value] == 1
    assert seed_channel.status == SeedChannelStatus.NOT_COMMUNITY.value
    assert seed_channel.community_id is None
    assert repository.communities == []


@pytest.mark.asyncio
async def test_transient_failure_marks_seed_failed() -> None:
    seed_group = _seed_group()
    seed_channel = _seed_channel(seed_group.id, username="flaky")
    repository = FakeSeedResolutionRepository(seed_group=seed_group, seeds=[seed_channel])
    resolver = FakeResolver({"flaky": TransientResolveError("temporary network error")})

    summary = await resolve_seed_group(
        repository,
        seed_group_id=seed_group.id,
        limit=100,
        retry_failed=False,
        resolver=resolver,
    )

    assert summary.counts()[SeedChannelStatus.FAILED.value] == 1
    assert seed_channel.status == SeedChannelStatus.FAILED.value
    assert seed_channel.community_id is None
    assert repository.communities == []


class FakeResolver:
    def __init__(self, outcomes: dict[str, TelegramResolveOutcome | Exception]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    async def resolve(self, username: str) -> TelegramResolveOutcome:
        self.calls.append(username)
        outcome = self.outcomes[username]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeSeedResolutionRepository:
    def __init__(
        self,
        *,
        seed_group: SeedGroup,
        seeds: list[SeedChannel],
        communities: list[Community] | None = None,
    ) -> None:
        self.seed_group = seed_group
        self.seeds = seeds
        self.communities = communities or []
        self.flush_count = 0

    async def get_seed_group(self, seed_group_id: UUID) -> SeedGroup | None:
        if seed_group_id == self.seed_group.id:
            return self.seed_group
        return None

    async def list_eligible_seed_channels(
        self,
        seed_group_id: UUID,
        *,
        statuses: list[str],
        limit: int,
    ) -> list[SeedChannel]:
        return [
            seed
            for seed in self.seeds
            if seed.seed_group_id == seed_group_id and seed.status in statuses
        ][:limit]

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        for community in self.communities:
            if community.tg_id == tg_id:
                return community
        return None

    async def add_community(self, community: Community) -> None:
        self.communities.append(community)

    async def flush(self) -> None:
        self.flush_count += 1


def _seed_group() -> SeedGroup:
    return SeedGroup(id=uuid4(), name="SaaS Seeds", normalized_name="saas seeds")


def _seed_channel(seed_group_id: UUID, *, username: str) -> SeedChannel:
    return SeedChannel(
        id=uuid4(),
        seed_group_id=seed_group_id,
        raw_value=f"@{username}",
        normalized_key=f"username:{username}",
        username=username,
        telegram_url=f"https://t.me/{username}",
        status=SeedChannelStatus.PENDING.value,
    )
