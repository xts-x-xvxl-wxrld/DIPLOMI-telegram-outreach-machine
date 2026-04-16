from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.db.enums import CommunitySource, CommunityStatus, SeedChannelStatus
from backend.db.models import Community, CommunityDiscoveryEdge, SeedChannel, SeedGroup
from backend.services.seed_expansion import (
    DiscoveredCommunityCandidate,
    NoResolvedSeedCommunities,
    expand_seed_group,
)


def test_community_discovery_edge_model_shape() -> None:
    table = CommunityDiscoveryEdge.__table__

    assert table.c.seed_group_id.foreign_keys
    assert table.c.seed_channel_id.foreign_keys
    assert table.c.source_community_id.foreign_keys
    assert table.c.target_community_id.foreign_keys
    assert table.c.evidence_type.nullable is False
    assert table.c.target_community_id.nullable is False
    assert "uq_community_discovery_edges_identity" in {
        constraint.name for constraint in table.constraints
    }


@pytest.mark.asyncio
async def test_seed_batch_expansion_creates_new_community_and_edge() -> None:
    seed_group = _seed_group()
    source = _community(tg_id=100, username="source", title="Source Channel")
    seed_channel = _resolved_seed(seed_group.id, source)
    repository = FakeSeedExpansionRepository(seed_group=seed_group, seeds=[seed_channel])
    adapter = FakeExpansionAdapter(
        [
            DiscoveredCommunityCandidate(
                tg_id=200,
                username="target",
                title="Target Community",
                description="A new related group",
                member_count=450,
                is_group=True,
                is_broadcast=False,
                evidence_type="mention",
                evidence_value="@target",
            )
        ]
    )

    summary = await expand_seed_group(
        repository,
        seed_group_id=seed_group.id,
        brief_id=None,
        depth=1,
        requested_by="operator",
        adapter=adapter,
    )

    target = repository.communities_by_tg_id[200]
    assert summary.new_communities == 1
    assert summary.edges_created == 1
    assert target.source == CommunitySource.EXPANSION.value
    assert target.status == CommunityStatus.CANDIDATE.value
    assert target.match_reason is not None
    assert "SaaS Seeds" in target.match_reason
    assert "mention: @target" in target.match_reason
    assert repository.edges[0].seed_group_id == seed_group.id
    assert repository.edges[0].seed_channel_id == seed_channel.id
    assert repository.edges[0].source_community_id == source.id
    assert repository.edges[0].target_community_id == target.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        CommunityStatus.APPROVED.value,
        CommunityStatus.REJECTED.value,
        CommunityStatus.MONITORING.value,
        CommunityStatus.DROPPED.value,
    ],
)
async def test_existing_community_preserves_operator_status(status: str) -> None:
    seed_group = _seed_group()
    source = _community(tg_id=100, username="source", title="Source Channel")
    existing = _community(tg_id=200, username="old_target", title="Old Target", status=status)
    seed_channel = _resolved_seed(seed_group.id, source)
    repository = FakeSeedExpansionRepository(
        seed_group=seed_group,
        seeds=[seed_channel],
        communities=[source, existing],
    )
    adapter = FakeExpansionAdapter(
        [
            DiscoveredCommunityCandidate(
                tg_id=200,
                username="target",
                title="Updated Target",
                description=None,
                member_count=999,
                is_group=False,
                is_broadcast=True,
                evidence_type="forward_source",
                evidence_value="post 123",
            )
        ]
    )

    summary = await expand_seed_group(
        repository,
        seed_group_id=seed_group.id,
        brief_id=uuid4(),
        depth=1,
        requested_by="operator",
        adapter=adapter,
    )

    assert summary.existing_communities == 1
    assert existing.status == status
    assert existing.username == "target"
    assert existing.title == "Updated Target"
    assert existing.member_count == 999


@pytest.mark.asyncio
async def test_duplicate_discovered_target_evidence_creates_one_edge() -> None:
    seed_group = _seed_group()
    source = _community(tg_id=100, username="source", title="Source Channel")
    seed_channel = _resolved_seed(seed_group.id, source)
    candidate = DiscoveredCommunityCandidate(
        tg_id=200,
        username="target",
        title="Target Community",
        description=None,
        member_count=None,
        is_group=True,
        is_broadcast=False,
        evidence_type="telegram_link",
        evidence_value=None,
    )
    repository = FakeSeedExpansionRepository(seed_group=seed_group, seeds=[seed_channel])
    adapter = FakeExpansionAdapter([candidate, candidate])

    summary = await expand_seed_group(
        repository,
        seed_group_id=seed_group.id,
        brief_id=None,
        depth=1,
        requested_by="operator",
        adapter=adapter,
    )

    assert summary.discovered_count == 2
    assert summary.edges_created == 1
    assert len(repository.edges) == 1


@pytest.mark.asyncio
async def test_seed_batch_context_appears_in_match_reason() -> None:
    seed_group = _seed_group()
    source = _community(tg_id=100, username="source", title="Source Channel")
    seed_channel = _resolved_seed(seed_group.id, source)
    repository = FakeSeedExpansionRepository(seed_group=seed_group, seeds=[seed_channel])
    adapter = FakeExpansionAdapter(
        [
            DiscoveredCommunityCandidate(
                tg_id=200,
                username="target",
                title="Target Community",
                description=None,
                member_count=None,
                is_group=True,
                is_broadcast=False,
                evidence_type="linked_discussion",
                evidence_value="discussion chat",
            )
        ]
    )

    await expand_seed_group(
        repository,
        seed_group_id=seed_group.id,
        brief_id=None,
        depth=1,
        requested_by="operator",
        adapter=adapter,
    )

    reason = repository.communities_by_tg_id[200].match_reason or ""
    assert "Expanded from seed group 'SaaS Seeds'" in reason
    assert "linked discussion: discussion chat" in reason
    assert "Source Channel" in reason


@pytest.mark.asyncio
async def test_empty_resolved_seed_group_fails_clearly() -> None:
    seed_group = _seed_group()
    repository = FakeSeedExpansionRepository(seed_group=seed_group, seeds=[])

    with pytest.raises(NoResolvedSeedCommunities):
        await expand_seed_group(
            repository,
            seed_group_id=seed_group.id,
            brief_id=None,
            depth=1,
            requested_by="operator",
            adapter=FakeExpansionAdapter([]),
        )


class FakeExpansionAdapter:
    def __init__(self, candidates: list[DiscoveredCommunityCandidate]) -> None:
        self.candidates = candidates
        self.calls: list[tuple[UUID, UUID, int]] = []

    async def discover_from_seed(
        self,
        *,
        seed_channel: SeedChannel,
        source_community: Community,
        depth: int,
    ) -> list[DiscoveredCommunityCandidate]:
        self.calls.append((seed_channel.id, source_community.id, depth))
        return self.candidates


class FakeSeedExpansionRepository:
    def __init__(
        self,
        *,
        seed_group: SeedGroup,
        seeds: list[SeedChannel],
        communities: list[Community] | None = None,
    ) -> None:
        self.seed_group = seed_group
        self.seeds = seeds
        self.communities_by_tg_id = {community.tg_id: community for community in communities or []}
        for seed in seeds:
            if seed.community is not None:
                self.communities_by_tg_id.setdefault(seed.community.tg_id, seed.community)
        self.edges: list[CommunityDiscoveryEdge] = []
        self.flush_count = 0

    async def get_seed_group(self, seed_group_id: UUID) -> SeedGroup | None:
        if seed_group_id == self.seed_group.id:
            return self.seed_group
        return None

    async def list_resolved_seed_channels(self, seed_group_id: UUID) -> list[SeedChannel]:
        return [
            seed
            for seed in self.seeds
            if seed.seed_group_id == seed_group_id
            and seed.status == SeedChannelStatus.RESOLVED.value
            and seed.community_id is not None
        ]

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        return self.communities_by_tg_id.get(tg_id)

    async def add_community(self, community: Community) -> None:
        self.communities_by_tg_id[community.tg_id] = community

    async def find_discovery_edge(
        self,
        *,
        seed_group_id: UUID,
        seed_channel_id: UUID,
        source_community_id: UUID,
        target_community_id: UUID,
        evidence_type: str,
        evidence_value: str | None,
    ) -> CommunityDiscoveryEdge | None:
        for edge in self.edges:
            if (
                edge.seed_group_id == seed_group_id
                and edge.seed_channel_id == seed_channel_id
                and edge.source_community_id == source_community_id
                and edge.target_community_id == target_community_id
                and edge.evidence_type == evidence_type
                and edge.evidence_value == evidence_value
            ):
                return edge
        return None

    async def add_discovery_edge(self, edge: CommunityDiscoveryEdge) -> None:
        self.edges.append(edge)

    async def flush(self) -> None:
        self.flush_count += 1


def _seed_group() -> SeedGroup:
    return SeedGroup(id=uuid4(), name="SaaS Seeds", normalized_name="saas seeds")


def _community(
    *,
    tg_id: int,
    username: str,
    title: str,
    status: str = CommunityStatus.CANDIDATE.value,
) -> Community:
    return Community(
        id=uuid4(),
        tg_id=tg_id,
        username=username,
        title=title,
        status=status,
        store_messages=False,
    )


def _resolved_seed(seed_group_id: UUID, community: Community) -> SeedChannel:
    seed_channel = SeedChannel(
        id=uuid4(),
        seed_group_id=seed_group_id,
        raw_value=f"@{community.username}",
        normalized_key=f"username:{community.username}",
        username=community.username,
        telegram_url=f"https://t.me/{community.username}",
        status=SeedChannelStatus.RESOLVED.value,
        community_id=community.id,
    )
    seed_channel.community = community
    return seed_channel
