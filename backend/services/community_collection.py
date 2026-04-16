from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import ActivityStatus, AnalysisStatus, CollectionRunStatus
from backend.db.models import CollectionRun, Community, CommunityMember, CommunitySnapshot, User


class CollectionError(RuntimeError):
    pass


class CommunityNotFound(CollectionError):
    pass


class CollectorAccountRateLimited(CollectionError):
    def __init__(self, flood_wait_seconds: int, message: str | None = None) -> None:
        self.flood_wait_seconds = flood_wait_seconds
        super().__init__(message or f"Telegram account rate limited for {flood_wait_seconds}s")


class CollectorAccountBanned(CollectionError):
    pass


@dataclass(frozen=True)
class TelegramMemberInfo:
    tg_user_id: int
    username: str | None = None
    first_name: str | None = None


@dataclass(frozen=True)
class TelegramCollectedCommunity:
    tg_id: int
    username: str | None
    title: str | None
    description: str | None
    member_count: int | None
    is_group: bool | None
    is_broadcast: bool | None


@dataclass(frozen=True)
class TelegramCommunityCollection:
    community: TelegramCollectedCommunity
    members: list[TelegramMemberInfo] = field(default_factory=list)
    member_limit_reached: bool = False
    collection_notes: list[str] = field(default_factory=list)


class TelegramCommunityCollector(Protocol):
    async def collect(self, community: Community, *, member_limit: int) -> TelegramCommunityCollection:
        pass


class CommunityCollectionRepository(Protocol):
    async def get_community(self, community_id: UUID) -> Community | None:
        pass

    async def get_user_by_tg_user_id(self, tg_user_id: int) -> User | None:
        pass

    async def add_user(self, user: User) -> None:
        pass

    async def get_community_member(self, community_id: UUID, user_id: UUID) -> CommunityMember | None:
        pass

    async def add_community_member(self, community_member: CommunityMember) -> None:
        pass

    async def add_snapshot(self, snapshot: CommunitySnapshot) -> None:
        pass

    async def add_collection_run(self, collection_run: CollectionRun) -> None:
        pass

    async def flush(self) -> None:
        pass


class SqlAlchemyCommunityCollectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_community(self, community_id: UUID) -> Community | None:
        return await self.session.get(Community, community_id)

    async def get_user_by_tg_user_id(self, tg_user_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.tg_user_id == tg_user_id))

    async def add_user(self, user: User) -> None:
        self.session.add(user)

    async def get_community_member(self, community_id: UUID, user_id: UUID) -> CommunityMember | None:
        return await self.session.scalar(
            select(CommunityMember).where(
                CommunityMember.community_id == community_id,
                CommunityMember.user_id == user_id,
            )
        )

    async def add_community_member(self, community_member: CommunityMember) -> None:
        self.session.add(community_member)

    async def add_snapshot(self, snapshot: CommunitySnapshot) -> None:
        self.session.add(snapshot)

    async def add_collection_run(self, collection_run: CollectionRun) -> None:
        self.session.add(collection_run)

    async def flush(self) -> None:
        await self.session.flush()


@dataclass(frozen=True)
class CommunityCollectionSummary:
    community_id: UUID
    collection_run_id: UUID
    snapshot_id: UUID | None
    members_seen: int
    member_limit_reached: bool
    status: str
    error_message: str | None = None
    collection_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "job_type": "collection.run",
            "community_id": str(self.community_id),
            "collection_run_id": str(self.collection_run_id),
            "snapshot_id": str(self.snapshot_id) if self.snapshot_id else None,
            "members_seen": self.members_seen,
            "member_limit_reached": self.member_limit_reached,
            "error_message": self.error_message,
            "collection_notes": list(self.collection_notes),
        }


async def collect_community(
    repository: CommunityCollectionRepository,
    *,
    community_id: UUID,
    collector: TelegramCommunityCollector,
    window_days: int,
    member_limit: int,
) -> CommunityCollectionSummary:
    community = await repository.get_community(community_id)
    if community is None:
        raise CommunityNotFound(f"Community not found: {community_id}")

    collected = await collector.collect(community, member_limit=max(member_limit, 1))
    return await persist_community_collection(
        repository,
        community=community,
        collected=collected,
        window_days=window_days,
    )


async def persist_community_collection(
    repository: CommunityCollectionRepository,
    *,
    community: Community,
    collected: TelegramCommunityCollection,
    window_days: int,
    now: datetime | None = None,
) -> CommunityCollectionSummary:
    current_time = now or _utcnow()
    _update_community_metadata(community, collected.community, snapshot_time=current_time)

    snapshot = CommunitySnapshot(
        id=uuid.uuid4(),
        community_id=community.id,
        member_count=collected.community.member_count,
        message_count_7d=0,
        collected_at=current_time,
    )
    await repository.add_snapshot(snapshot)

    unique_members = _unique_members(collected.members)
    for member in unique_members:
        await _upsert_member(repository, community_id=community.id, member=member, now=current_time)

    collection_run = CollectionRun(
        id=uuid.uuid4(),
        community_id=community.id,
        brief_id=community.brief_id,
        status=CollectionRunStatus.COMPLETED.value,
        analysis_status=AnalysisStatus.SKIPPED.value,
        window_days=window_days,
        window_start=None,
        window_end=current_time,
        messages_seen=0,
        members_seen=len(unique_members),
        activity_events=0,
        snapshot_id=snapshot.id,
        analysis_input=None,
        analysis_input_expires_at=None,
        completed_at=current_time,
    )
    await repository.add_collection_run(collection_run)
    await repository.flush()

    return CommunityCollectionSummary(
        community_id=community.id,
        collection_run_id=collection_run.id,
        snapshot_id=snapshot.id,
        members_seen=len(unique_members),
        member_limit_reached=collected.member_limit_reached,
        status=CollectionRunStatus.COMPLETED.value,
        collection_notes=tuple(collected.collection_notes),
    )


async def record_collection_failure(
    repository: CommunityCollectionRepository,
    *,
    community_id: UUID,
    window_days: int,
    error_message: str,
    now: datetime | None = None,
) -> CommunityCollectionSummary | None:
    community = await repository.get_community(community_id)
    if community is None:
        return None

    current_time = now or _utcnow()
    collection_run = CollectionRun(
        id=uuid.uuid4(),
        community_id=community.id,
        brief_id=community.brief_id,
        status=CollectionRunStatus.FAILED.value,
        analysis_status=AnalysisStatus.SKIPPED.value,
        window_days=window_days,
        window_start=None,
        window_end=current_time,
        messages_seen=0,
        members_seen=0,
        activity_events=0,
        snapshot_id=None,
        analysis_input=None,
        analysis_input_expires_at=None,
        error_message=error_message[:1000],
        completed_at=current_time,
    )
    await repository.add_collection_run(collection_run)
    await repository.flush()
    return CommunityCollectionSummary(
        community_id=community.id,
        collection_run_id=collection_run.id,
        snapshot_id=None,
        members_seen=0,
        member_limit_reached=False,
        status=CollectionRunStatus.FAILED.value,
        error_message=error_message[:1000],
    )


def _update_community_metadata(
    community: Community,
    collected: TelegramCollectedCommunity,
    *,
    snapshot_time: datetime,
) -> None:
    community.tg_id = collected.tg_id
    if collected.username is not None:
        community.username = collected.username
    if collected.title is not None:
        community.title = collected.title
    if collected.description is not None:
        community.description = collected.description
    if collected.member_count is not None:
        community.member_count = collected.member_count
    if collected.is_group is not None:
        community.is_group = collected.is_group
    if collected.is_broadcast is not None:
        community.is_broadcast = collected.is_broadcast
    community.last_snapshot_at = snapshot_time


async def _upsert_member(
    repository: CommunityCollectionRepository,
    *,
    community_id: UUID,
    member: TelegramMemberInfo,
    now: datetime,
) -> None:
    user = await repository.get_user_by_tg_user_id(member.tg_user_id)
    if user is None:
        user = User(
            id=uuid.uuid4(),
            tg_user_id=member.tg_user_id,
            username=member.username,
            first_name=member.first_name,
            first_seen_at=now,
            last_updated_at=now,
        )
        await repository.add_user(user)
    else:
        if member.username is not None:
            user.username = member.username
        if member.first_name is not None:
            user.first_name = member.first_name
        user.last_updated_at = now

    community_member = await repository.get_community_member(community_id, user.id)
    if community_member is None:
        community_member = CommunityMember(
            id=uuid.uuid4(),
            community_id=community_id,
            user_id=user.id,
            activity_status=ActivityStatus.INACTIVE.value,
            event_count=0,
            first_seen_at=now,
            last_updated_at=now,
        )
        await repository.add_community_member(community_member)
    else:
        community_member.last_updated_at = now


def _unique_members(members: list[TelegramMemberInfo]) -> list[TelegramMemberInfo]:
    unique: dict[int, TelegramMemberInfo] = {}
    for member in members:
        unique[member.tg_user_id] = member
    return list(unique.values())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
