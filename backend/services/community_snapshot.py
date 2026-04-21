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


class CommunitySnapshotError(RuntimeError):
    pass


class CommunityNotFound(CommunitySnapshotError):
    pass


class SnapshotAccountRateLimited(CommunitySnapshotError):
    def __init__(self, flood_wait_seconds: int, message: str | None = None) -> None:
        self.flood_wait_seconds = flood_wait_seconds
        super().__init__(message or f"Telegram account rate limited for {flood_wait_seconds}s")


class SnapshotAccountBanned(CommunitySnapshotError):
    pass


@dataclass(frozen=True)
class TelegramMemberInfo:
    tg_user_id: int
    username: str | None = None
    first_name: str | None = None


@dataclass(frozen=True)
class TelegramSnapshotCommunity:
    tg_id: int
    username: str | None
    title: str | None
    description: str | None
    member_count: int | None
    is_group: bool | None
    is_broadcast: bool | None


@dataclass(frozen=True)
class TelegramCommunitySnapshot:
    community: TelegramSnapshotCommunity
    members: list[TelegramMemberInfo] = field(default_factory=list)
    member_limit_reached: bool = False
    snapshot_notes: list[str] = field(default_factory=list)


class TelegramCommunitySnapshotter(Protocol):
    async def snapshot(self, community: Community, *, member_limit: int) -> TelegramCommunitySnapshot:
        pass


class CommunitySnapshotRepository(Protocol):
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


class SqlAlchemyCommunitySnapshotRepository:
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
class CommunitySnapshotJobSummary:
    community_id: UUID
    collection_run_id: UUID
    snapshot_id: UUID | None
    members_seen: int
    member_limit_reached: bool
    status: str
    error_message: str | None = None
    snapshot_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "job_type": "community.snapshot",
            "community_id": str(self.community_id),
            "collection_run_id": str(self.collection_run_id),
            "snapshot_id": str(self.snapshot_id) if self.snapshot_id else None,
            "members_seen": self.members_seen,
            "member_limit_reached": self.member_limit_reached,
            "error_message": self.error_message,
            "snapshot_notes": list(self.snapshot_notes),
        }


async def snapshot_community(
    repository: CommunitySnapshotRepository,
    *,
    community_id: UUID,
    snapshotter: TelegramCommunitySnapshotter,
    window_days: int,
    member_limit: int,
) -> CommunitySnapshotJobSummary:
    community = await repository.get_community(community_id)
    if community is None:
        raise CommunityNotFound(f"Community not found: {community_id}")

    captured = await snapshotter.snapshot(community, member_limit=max(member_limit, 1))
    return await persist_community_snapshot(
        repository,
        community=community,
        captured=captured,
        window_days=window_days,
    )


async def persist_community_snapshot(
    repository: CommunitySnapshotRepository,
    *,
    community: Community,
    captured: TelegramCommunitySnapshot,
    window_days: int,
    now: datetime | None = None,
) -> CommunitySnapshotJobSummary:
    current_time = now or _utcnow()
    _update_community_metadata(community, captured.community, snapshot_time=current_time)

    snapshot = CommunitySnapshot(
        id=uuid.uuid4(),
        community_id=community.id,
        member_count=captured.community.member_count,
        message_count_7d=0,
        collected_at=current_time,
    )
    await repository.add_snapshot(snapshot)

    unique_members = _unique_members(captured.members)
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

    return CommunitySnapshotJobSummary(
        community_id=community.id,
        collection_run_id=collection_run.id,
        snapshot_id=snapshot.id,
        members_seen=len(unique_members),
        member_limit_reached=captured.member_limit_reached,
        status=CollectionRunStatus.COMPLETED.value,
        snapshot_notes=tuple(captured.snapshot_notes),
    )


async def record_snapshot_failure(
    repository: CommunitySnapshotRepository,
    *,
    community_id: UUID,
    window_days: int,
    error_message: str,
    now: datetime | None = None,
) -> CommunitySnapshotJobSummary | None:
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
    return CommunitySnapshotJobSummary(
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
    captured: TelegramSnapshotCommunity,
    *,
    snapshot_time: datetime,
) -> None:
    community.tg_id = captured.tg_id
    if captured.username is not None:
        community.username = captured.username
    if captured.title is not None:
        community.title = captured.title
    if captured.description is not None:
        community.description = captured.description
    if captured.member_count is not None:
        community.member_count = captured.member_count
    if captured.is_group is not None:
        community.is_group = captured.is_group
    if captured.is_broadcast is not None:
        community.is_broadcast = captured.is_broadcast
    community.last_snapshot_at = snapshot_time


async def _upsert_member(
    repository: CommunitySnapshotRepository,
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
