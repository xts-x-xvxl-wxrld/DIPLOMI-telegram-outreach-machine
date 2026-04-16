from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import CommunitySource, CommunityStatus, SeedChannelStatus
from backend.db.models import Community, SeedChannel, SeedGroup

ResolutionStatus = Literal[
    "resolved",
    "invalid",
    "inaccessible",
    "not_community",
    "failed",
]

OPERATOR_COMMUNITY_STATUSES = {
    CommunityStatus.APPROVED.value,
    CommunityStatus.REJECTED.value,
    CommunityStatus.MONITORING.value,
    CommunityStatus.DROPPED.value,
}


class SeedResolutionError(RuntimeError):
    pass


class SeedGroupNotFound(SeedResolutionError):
    pass


class TransientResolveError(SeedResolutionError):
    pass


class ResolverAccountRateLimited(SeedResolutionError):
    def __init__(self, flood_wait_seconds: int, message: str | None = None) -> None:
        self.flood_wait_seconds = flood_wait_seconds
        super().__init__(message or f"Telegram account rate limited for {flood_wait_seconds}s")


class ResolverAccountBanned(SeedResolutionError):
    pass


@dataclass(frozen=True)
class TelegramCommunityInfo:
    tg_id: int
    username: str | None
    title: str | None
    description: str | None
    member_count: int | None
    is_group: bool
    is_broadcast: bool


@dataclass(frozen=True)
class TelegramResolveOutcome:
    status: ResolutionStatus
    community: TelegramCommunityInfo | None = None
    error_message: str | None = None

    @classmethod
    def resolved(cls, community: TelegramCommunityInfo) -> "TelegramResolveOutcome":
        return cls(status=SeedChannelStatus.RESOLVED.value, community=community)

    @classmethod
    def inaccessible(cls, message: str | None = None) -> "TelegramResolveOutcome":
        return cls(status=SeedChannelStatus.INACCESSIBLE.value, error_message=message)

    @classmethod
    def not_community(cls, message: str | None = None) -> "TelegramResolveOutcome":
        return cls(status=SeedChannelStatus.NOT_COMMUNITY.value, error_message=message)

    @classmethod
    def failed(cls, message: str | None = None) -> "TelegramResolveOutcome":
        return cls(status=SeedChannelStatus.FAILED.value, error_message=message)

    @classmethod
    def invalid(cls, message: str | None = None) -> "TelegramResolveOutcome":
        return cls(status=SeedChannelStatus.INVALID.value, error_message=message)


class TelegramResolverAdapter(Protocol):
    async def resolve(self, username: str) -> TelegramResolveOutcome:
        pass


class SeedResolutionRepository(Protocol):
    async def get_seed_group(self, seed_group_id: UUID) -> SeedGroup | None:
        pass

    async def list_eligible_seed_channels(
        self,
        seed_group_id: UUID,
        *,
        statuses: list[str],
        limit: int,
    ) -> list[SeedChannel]:
        pass

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        pass

    async def add_community(self, community: Community) -> None:
        pass

    async def flush(self) -> None:
        pass


class SqlAlchemySeedResolutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_seed_group(self, seed_group_id: UUID) -> SeedGroup | None:
        return await self.session.get(SeedGroup, seed_group_id)

    async def list_eligible_seed_channels(
        self,
        seed_group_id: UUID,
        *,
        statuses: list[str],
        limit: int,
    ) -> list[SeedChannel]:
        rows = await self.session.scalars(
            select(SeedChannel)
            .where(SeedChannel.seed_group_id == seed_group_id)
            .where(SeedChannel.status.in_(statuses))
            .order_by(SeedChannel.created_at, SeedChannel.id)
            .limit(limit)
        )
        return list(rows)

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        return await self.session.scalar(select(Community).where(Community.tg_id == tg_id))

    async def add_community(self, community: Community) -> None:
        self.session.add(community)

    async def flush(self) -> None:
        await self.session.flush()


@dataclass(frozen=True)
class SeedResolutionRowResult:
    seed_channel_id: UUID
    username: str | None
    status: ResolutionStatus
    community_id: UUID | None = None
    error_message: str | None = None


@dataclass
class SeedResolutionSummary:
    seed_group_id: UUID
    results: list[SeedResolutionRowResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    def counts(self) -> dict[str, int]:
        counts = {
            SeedChannelStatus.RESOLVED.value: 0,
            SeedChannelStatus.INVALID.value: 0,
            SeedChannelStatus.INACCESSIBLE.value: 0,
            SeedChannelStatus.NOT_COMMUNITY.value: 0,
            SeedChannelStatus.FAILED.value: 0,
        }
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        return counts

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "processed",
            "job_type": "seed.resolve",
            "seed_group_id": str(self.seed_group_id),
            "total": self.total,
            "counts": self.counts(),
            "results": [
                {
                    "seed_channel_id": str(result.seed_channel_id),
                    "username": result.username,
                    "status": result.status,
                    "community_id": str(result.community_id) if result.community_id else None,
                    "error_message": result.error_message,
                }
                for result in self.results
            ],
        }


async def resolve_seed_group(
    repository: SeedResolutionRepository,
    *,
    seed_group_id: UUID,
    limit: int,
    retry_failed: bool,
    resolver: TelegramResolverAdapter,
) -> SeedResolutionSummary:
    seed_group = await repository.get_seed_group(seed_group_id)
    if seed_group is None:
        raise SeedGroupNotFound(f"Seed group not found: {seed_group_id}")

    seed_channels = await repository.list_eligible_seed_channels(
        seed_group_id,
        statuses=_eligible_statuses(retry_failed=retry_failed),
        limit=max(limit, 1),
    )
    summary = SeedResolutionSummary(seed_group_id=seed_group_id)

    for seed_channel in seed_channels:
        outcome = await _resolve_seed_channel(seed_channel, resolver)
        if outcome.status == SeedChannelStatus.RESOLVED.value:
            if outcome.community is None:
                outcome = TelegramResolveOutcome.failed("Resolver returned no community data")
            else:
                community = await _upsert_manual_community(
                    repository,
                    seed_group,
                    seed_channel,
                    outcome.community,
                )
                seed_channel.status = SeedChannelStatus.RESOLVED.value
                seed_channel.community_id = community.id
                summary.results.append(
                    SeedResolutionRowResult(
                        seed_channel_id=seed_channel.id,
                        username=seed_channel.username,
                        status=SeedChannelStatus.RESOLVED.value,
                        community_id=community.id,
                    )
                )
                continue

        seed_channel.status = outcome.status
        seed_channel.community_id = None
        summary.results.append(
            SeedResolutionRowResult(
                seed_channel_id=seed_channel.id,
                username=seed_channel.username,
                status=outcome.status,
                error_message=outcome.error_message,
            )
        )

    await repository.flush()
    return summary


async def _resolve_seed_channel(
    seed_channel: SeedChannel,
    resolver: TelegramResolverAdapter,
) -> TelegramResolveOutcome:
    if not seed_channel.username:
        return TelegramResolveOutcome.invalid("Seed row has no public Telegram username")

    try:
        return await resolver.resolve(seed_channel.username)
    except TransientResolveError as exc:
        return TelegramResolveOutcome.failed(str(exc))


async def _upsert_manual_community(
    repository: SeedResolutionRepository,
    seed_group: SeedGroup,
    seed_channel: SeedChannel,
    resolved: TelegramCommunityInfo,
) -> Community:
    community = await repository.get_community_by_tg_id(resolved.tg_id)
    if community is None:
        community = Community(
            id=uuid.uuid4(),
            tg_id=resolved.tg_id,
            status=CommunityStatus.CANDIDATE.value,
            store_messages=False,
        )
        await repository.add_community(community)

    community.username = resolved.username or seed_channel.username or community.username
    community.title = resolved.title or seed_channel.title or community.title
    if resolved.description is not None:
        community.description = resolved.description
    if resolved.member_count is not None:
        community.member_count = resolved.member_count
    community.is_group = resolved.is_group
    community.is_broadcast = resolved.is_broadcast
    community.source = CommunitySource.MANUAL.value
    community.match_reason = f"Imported manual seed: {seed_group.name}"

    if community.status in OPERATOR_COMMUNITY_STATUSES:
        return community
    if not community.status:
        community.status = CommunityStatus.CANDIDATE.value
    return community


def _eligible_statuses(*, retry_failed: bool) -> list[str]:
    statuses = [SeedChannelStatus.PENDING.value]
    if retry_failed:
        statuses.extend([SeedChannelStatus.FAILED.value, SeedChannelStatus.INACCESSIBLE.value])
    return statuses
