from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.enums import CommunitySource, CommunityStatus, SeedChannelStatus
from backend.db.models import Community, CommunityDiscoveryEdge, SeedChannel, SeedGroup
from backend.services.seed_resolution import OPERATOR_COMMUNITY_STATUSES


class SeedExpansionError(RuntimeError):
    pass


class SeedExpansionGroupNotFound(SeedExpansionError):
    pass


class NoResolvedSeedCommunities(SeedExpansionError):
    pass


class ExpansionAccountRateLimited(SeedExpansionError):
    def __init__(self, flood_wait_seconds: int, message: str | None = None) -> None:
        self.flood_wait_seconds = flood_wait_seconds
        super().__init__(message or f"Telegram account rate limited for {flood_wait_seconds}s")


class ExpansionAccountBanned(SeedExpansionError):
    pass


@dataclass(frozen=True)
class DiscoveredCommunityCandidate:
    tg_id: int
    username: str | None
    title: str | None
    description: str | None
    member_count: int | None
    is_group: bool
    is_broadcast: bool
    evidence_type: str
    evidence_value: str | None = None


class SeedExpansionAdapter(Protocol):
    async def discover_from_seed(
        self,
        *,
        seed_channel: SeedChannel,
        source_community: Community,
        depth: int,
    ) -> list[DiscoveredCommunityCandidate]:
        pass


class SeedExpansionRepository(Protocol):
    async def get_seed_group(self, seed_group_id: UUID) -> SeedGroup | None:
        pass

    async def list_resolved_seed_channels(self, seed_group_id: UUID) -> list[SeedChannel]:
        pass

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        pass

    async def add_community(self, community: Community) -> None:
        pass

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
        pass

    async def add_discovery_edge(self, edge: CommunityDiscoveryEdge) -> None:
        pass

    async def flush(self) -> None:
        pass


class SqlAlchemySeedExpansionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_seed_group(self, seed_group_id: UUID) -> SeedGroup | None:
        return await self.session.get(SeedGroup, seed_group_id)

    async def list_resolved_seed_channels(self, seed_group_id: UUID) -> list[SeedChannel]:
        rows = await self.session.scalars(
            select(SeedChannel)
            .where(SeedChannel.seed_group_id == seed_group_id)
            .where(SeedChannel.status == SeedChannelStatus.RESOLVED.value)
            .where(SeedChannel.community_id.is_not(None))
            .options(selectinload(SeedChannel.community))
            .order_by(SeedChannel.created_at, SeedChannel.id)
        )
        return list(rows)

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        return await self.session.scalar(select(Community).where(Community.tg_id == tg_id))

    async def add_community(self, community: Community) -> None:
        self.session.add(community)

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
        evidence_filter = (
            CommunityDiscoveryEdge.evidence_value.is_(None)
            if evidence_value is None
            else CommunityDiscoveryEdge.evidence_value == evidence_value
        )
        return await self.session.scalar(
            select(CommunityDiscoveryEdge)
            .where(CommunityDiscoveryEdge.seed_group_id == seed_group_id)
            .where(CommunityDiscoveryEdge.seed_channel_id == seed_channel_id)
            .where(CommunityDiscoveryEdge.source_community_id == source_community_id)
            .where(CommunityDiscoveryEdge.target_community_id == target_community_id)
            .where(CommunityDiscoveryEdge.evidence_type == evidence_type)
            .where(evidence_filter)
            .limit(1)
        )

    async def add_discovery_edge(self, edge: CommunityDiscoveryEdge) -> None:
        self.session.add(edge)

    async def flush(self) -> None:
        await self.session.flush()


@dataclass
class SeedExpansionSummary:
    seed_group_id: UUID
    seeds_expanded: int = 0
    discovered_count: int = 0
    new_communities: int = 0
    existing_communities: int = 0
    edges_created: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "processed",
            "job_type": "seed.expand",
            "seed_group_id": str(self.seed_group_id),
            "seeds_expanded": self.seeds_expanded,
            "discovered_count": self.discovered_count,
            "new_communities": self.new_communities,
            "existing_communities": self.existing_communities,
            "edges_created": self.edges_created,
        }


async def expand_seed_group(
    repository: SeedExpansionRepository,
    *,
    seed_group_id: UUID,
    brief_id: UUID | None,
    depth: int,
    requested_by: str,
    adapter: SeedExpansionAdapter,
) -> SeedExpansionSummary:
    seed_group = await repository.get_seed_group(seed_group_id)
    if seed_group is None:
        raise SeedExpansionGroupNotFound(f"Seed group not found: {seed_group_id}")

    seed_channels = [
        seed_channel
        for seed_channel in await repository.list_resolved_seed_channels(seed_group_id)
        if seed_channel.community is not None
    ]
    if not seed_channels:
        raise NoResolvedSeedCommunities("Seed group has no resolved communities yet")

    summary = SeedExpansionSummary(seed_group_id=seed_group_id, seeds_expanded=len(seed_channels))
    normalized_depth = max(depth, 1)

    for seed_channel in seed_channels:
        source_community = seed_channel.community
        candidates = await adapter.discover_from_seed(
            seed_channel=seed_channel,
            source_community=source_community,
            depth=normalized_depth,
        )
        for candidate in candidates:
            summary.discovered_count += 1
            community, created = await _upsert_discovered_community(
                repository,
                seed_group=seed_group,
                seed_channel=seed_channel,
                source_community=source_community,
                candidate=candidate,
                brief_id=brief_id,
            )
            if created:
                summary.new_communities += 1
            else:
                summary.existing_communities += 1
            if await _ensure_discovery_edge(
                repository,
                seed_group=seed_group,
                seed_channel=seed_channel,
                source_community=source_community,
                target_community=community,
                candidate=candidate,
            ):
                summary.edges_created += 1

    await repository.flush()
    return summary


async def _upsert_discovered_community(
    repository: SeedExpansionRepository,
    *,
    seed_group: SeedGroup,
    seed_channel: SeedChannel,
    source_community: Community,
    candidate: DiscoveredCommunityCandidate,
    brief_id: UUID | None,
) -> tuple[Community, bool]:
    community = await repository.get_community_by_tg_id(candidate.tg_id)
    created = community is None
    if community is None:
        community = Community(
            id=uuid.uuid4(),
            tg_id=candidate.tg_id,
            source=CommunitySource.EXPANSION.value,
            status=CommunityStatus.CANDIDATE.value,
            brief_id=brief_id,
            store_messages=False,
        )
        await repository.add_community(community)

    community.username = candidate.username or community.username
    community.title = candidate.title or community.title
    if candidate.description is not None:
        community.description = candidate.description
    if candidate.member_count is not None:
        community.member_count = candidate.member_count
    community.is_group = candidate.is_group
    community.is_broadcast = candidate.is_broadcast
    if not community.source:
        community.source = CommunitySource.EXPANSION.value
    if community.brief_id is None and brief_id is not None:
        community.brief_id = brief_id

    reason = _match_reason(
        seed_group=seed_group,
        seed_channel=seed_channel,
        source_community=source_community,
        candidate=candidate,
    )
    if reason not in (community.match_reason or ""):
        community.match_reason = f"{community.match_reason}; {reason}" if community.match_reason else reason

    if community.status not in OPERATOR_COMMUNITY_STATUSES and not community.status:
        community.status = CommunityStatus.CANDIDATE.value
    return community, created


async def _ensure_discovery_edge(
    repository: SeedExpansionRepository,
    *,
    seed_group: SeedGroup,
    seed_channel: SeedChannel,
    source_community: Community,
    target_community: Community,
    candidate: DiscoveredCommunityCandidate,
) -> bool:
    existing = await repository.find_discovery_edge(
        seed_group_id=seed_group.id,
        seed_channel_id=seed_channel.id,
        source_community_id=source_community.id,
        target_community_id=target_community.id,
        evidence_type=candidate.evidence_type,
        evidence_value=candidate.evidence_value,
    )
    if existing is not None:
        return False

    await repository.add_discovery_edge(
        CommunityDiscoveryEdge(
            id=uuid.uuid4(),
            seed_group_id=seed_group.id,
            seed_channel_id=seed_channel.id,
            source_community_id=source_community.id,
            target_community_id=target_community.id,
            evidence_type=candidate.evidence_type,
            evidence_value=candidate.evidence_value,
        )
    )
    return True


def _match_reason(
    *,
    seed_group: SeedGroup,
    seed_channel: SeedChannel,
    source_community: Community,
    candidate: DiscoveredCommunityCandidate,
) -> str:
    source_label = source_community.title or source_community.username or seed_channel.username or "resolved seed"
    evidence = candidate.evidence_type.replace("_", " ")
    if candidate.evidence_value:
        evidence = f"{evidence}: {candidate.evidence_value}"
    return f"Expanded from seed group '{seed_group.name}' via {evidence} from {source_label}"
