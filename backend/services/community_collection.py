from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import ActivityStatus, AnalysisStatus, CollectionRunStatus, EngagementMode
from backend.db.models import (
    CollectionRun,
    Community,
    CommunityMember,
    CommunitySnapshot,
    Message,
    User,
)
from backend.services.community_engagement import (
    get_engagement_settings,
    has_engagement_target_permission,
)

MAX_ENGAGEMENT_MESSAGES = 100
MAX_ENGAGEMENT_MESSAGE_CHARS = 500
CHECKPOINT_OVERLAP = 5
ANALYSIS_INPUT_RETENTION_HOURS = 48
ENABLED_DETECTION_MODES = {
    EngagementMode.OBSERVE.value,
    EngagementMode.SUGGEST.value,
    EngagementMode.REQUIRE_APPROVAL.value,
}


class CollectionError(RuntimeError):
    pass


class CollectionCommunityNotFound(CollectionError):
    pass


class CollectionCommunityInaccessible(CollectionError):
    pass


class CollectionAccountRateLimited(CollectionError):
    def __init__(self, flood_wait_seconds: int, message: str | None = None) -> None:
        self.flood_wait_seconds = flood_wait_seconds
        super().__init__(message or f"Telegram account rate limited for {flood_wait_seconds}s")


class CollectionAccountBanned(CollectionError):
    pass


@dataclass(frozen=True)
class TelegramCollectedUser:
    tg_user_id: int
    username: str | None = None
    first_name: str | None = None


@dataclass(frozen=True)
class TelegramCollectedMessage:
    tg_message_id: int
    text: str | None
    message_date: datetime
    message_type: str = "text"
    sender: TelegramCollectedUser | None = None
    reply_to_tg_message_id: int | None = None
    reply_context: str | None = None
    is_replyable: bool = True
    has_forward: bool | None = None
    forward_from_id: int | None = None
    views: int | None = None
    reactions_count: int | None = None


@dataclass(frozen=True)
class TelegramCollectionMetadata:
    title: str | None = None
    username: str | None = None
    description: str | None = None
    member_count: int | None = None
    is_group: bool | None = None
    is_broadcast: bool | None = None
    message_count_7d: int | None = None


@dataclass(frozen=True)
class TelegramCollectionBatch:
    messages: list[TelegramCollectedMessage] = field(default_factory=list)
    metadata: TelegramCollectionMetadata | None = None


class TelegramEngagementCollector(Protocol):
    async def collect_messages(
        self,
        community: Community,
        *,
        after_tg_message_id: int | None,
        limit: int,
    ) -> TelegramCollectionBatch:
        pass


@dataclass(frozen=True)
class CollectionJobSummary:
    community_id: UUID
    collection_run_id: UUID
    status: str
    messages_seen: int
    detection_messages: int
    members_seen: int
    activity_events: int
    snapshot_id: UUID | None
    should_enqueue_detection: bool = False
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "job_type": "collection.run",
            "community_id": str(self.community_id),
            "collection_run_id": str(self.collection_run_id),
            "messages_seen": self.messages_seen,
            "detection_messages": self.detection_messages,
            "members_seen": self.members_seen,
            "activity_events": self.activity_events,
            "snapshot_id": str(self.snapshot_id) if self.snapshot_id else None,
            "should_enqueue_detection": self.should_enqueue_detection,
            "error_message": self.error_message,
        }


async def collect_community_engagement_messages(
    session: AsyncSession,
    *,
    community_id: UUID,
    collector: TelegramEngagementCollector,
    reason: str,
    window_days: int,
    now: datetime | None = None,
) -> CollectionJobSummary:
    current_time = _ensure_aware_utc(now or datetime.now(timezone.utc))
    community = await session.get(Community, community_id)
    if community is None:
        raise CollectionCommunityNotFound(f"Community not found: {community_id}")

    engagement_settings = await get_engagement_settings(session, community_id)
    has_detect_permission = await has_engagement_target_permission(
        session,
        community_id=community_id,
        permission="detect",
    )
    if not has_detect_permission:
        raise CollectionCommunityInaccessible("engagement target is not approved for detection")

    previous_checkpoint = await _latest_engagement_checkpoint(session, community_id=community_id)
    after_id = _overlap_checkpoint(previous_checkpoint.get("through_tg_message_id_inclusive"))
    batch = await collector.collect_messages(community, after_tg_message_id=after_id, limit=MAX_ENGAGEMENT_MESSAGES)
    _update_community_metadata(community, batch.metadata, now=current_time)

    messages = _dedupe_new_messages(
        batch.messages,
        previous_through_id=previous_checkpoint.get("through_tg_message_id_inclusive"),
    )
    detection_messages = [_message_artifact(message) for message in messages if _is_detection_eligible(message)]
    snapshot = CommunitySnapshot(
        id=uuid.uuid4(),
        community_id=community.id,
        member_count=batch.metadata.member_count if batch.metadata else community.member_count,
        message_count_7d=batch.metadata.message_count_7d if batch.metadata else None,
        collected_at=current_time,
    )
    session.add(snapshot)
    await session.flush()

    unique_senders = _unique_senders(messages)
    for sender in unique_senders:
        await _upsert_active_member(session, community_id=community.id, sender=sender, now=current_time)

    if community.store_messages:
        for message in messages:
            await _add_stored_message(session, community=community, message=message, now=current_time)

    checkpoint = _build_checkpoint(previous_checkpoint, messages)
    analysis_input = {
        "engagement_checkpoint": checkpoint,
        "engagement_messages": detection_messages[-MAX_ENGAGEMENT_MESSAGES:],
    }
    collection_run = CollectionRun(
        id=uuid.uuid4(),
        community_id=community.id,
        brief_id=community.brief_id,
        status=CollectionRunStatus.COMPLETED.value,
        analysis_status=AnalysisStatus.SKIPPED.value,
        window_days=window_days,
        window_start=current_time - timedelta(days=window_days),
        window_end=current_time,
        messages_seen=len(messages),
        members_seen=len(unique_senders),
        activity_events=len([message for message in messages if message.sender is not None]),
        snapshot_id=snapshot.id,
        analysis_input=analysis_input,
        analysis_input_expires_at=current_time + timedelta(hours=ANALYSIS_INPUT_RETENTION_HOURS),
        completed_at=current_time,
    )
    session.add(collection_run)
    await session.flush()

    return CollectionJobSummary(
        community_id=community.id,
        collection_run_id=collection_run.id,
        status=CollectionRunStatus.COMPLETED.value,
        messages_seen=len(messages),
        detection_messages=len(detection_messages),
        members_seen=len(unique_senders),
        activity_events=collection_run.activity_events,
        snapshot_id=snapshot.id,
        should_enqueue_detection=_should_enqueue_detection(
            reason=reason,
            detection_messages=len(detection_messages),
            settings_mode=engagement_settings.mode,
            has_detect_permission=has_detect_permission,
            now=current_time,
            quiet_hours_start=engagement_settings.quiet_hours_start,
            quiet_hours_end=engagement_settings.quiet_hours_end,
        ),
    )


async def record_collection_failure(
    session: AsyncSession,
    *,
    community_id: UUID,
    window_days: int,
    error_message: str,
    now: datetime | None = None,
) -> CollectionJobSummary | None:
    community = await session.get(Community, community_id)
    if community is None:
        return None

    current_time = _ensure_aware_utc(now or datetime.now(timezone.utc))
    collection_run = CollectionRun(
        id=uuid.uuid4(),
        community_id=community.id,
        brief_id=community.brief_id,
        status=CollectionRunStatus.FAILED.value,
        analysis_status=AnalysisStatus.SKIPPED.value,
        window_days=window_days,
        window_start=current_time - timedelta(days=window_days),
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
    session.add(collection_run)
    await session.flush()
    return CollectionJobSummary(
        community_id=community.id,
        collection_run_id=collection_run.id,
        status=CollectionRunStatus.FAILED.value,
        messages_seen=0,
        detection_messages=0,
        members_seen=0,
        activity_events=0,
        snapshot_id=None,
        error_message=error_message[:1000],
    )


async def _latest_engagement_checkpoint(
    session: AsyncSession,
    *,
    community_id: UUID,
) -> dict[str, int | str | None]:
    result = await session.scalars(
        select(CollectionRun)
        .where(
            CollectionRun.community_id == community_id,
            CollectionRun.status == CollectionRunStatus.COMPLETED.value,
            CollectionRun.analysis_input.is_not(None),
        )
        .order_by(CollectionRun.completed_at.desc().nullslast(), CollectionRun.started_at.desc())
        .limit(5)
    )
    for run in result:
        analysis_input = run.analysis_input or {}
        checkpoint = analysis_input.get("engagement_checkpoint")
        if isinstance(checkpoint, dict):
            return checkpoint
    return {}


def _dedupe_new_messages(
    messages: list[TelegramCollectedMessage],
    *,
    previous_through_id: object,
) -> list[TelegramCollectedMessage]:
    previous_id = _optional_int(previous_through_id)
    unique: dict[int, TelegramCollectedMessage] = {}
    for message in messages:
        if previous_id is not None and message.tg_message_id <= previous_id:
            continue
        if not message.text or not message.text.strip():
            continue
        unique[message.tg_message_id] = message
    return sorted(unique.values(), key=lambda item: (item.message_date, item.tg_message_id))


def _message_artifact(message: TelegramCollectedMessage) -> dict[str, object]:
    return {
        "tg_message_id": message.tg_message_id,
        "text": _truncate(message.text, MAX_ENGAGEMENT_MESSAGE_CHARS),
        "message_date": _ensure_aware_utc(message.message_date).isoformat(),
        "reply_to_tg_message_id": message.reply_to_tg_message_id,
        "reply_context": _truncate(message.reply_context, MAX_ENGAGEMENT_MESSAGE_CHARS)
        if message.reply_context
        else None,
        "is_replyable": bool(message.is_replyable),
        "message_type": message.message_type,
    }


def _is_detection_eligible(message: TelegramCollectedMessage) -> bool:
    return bool(message.text and message.text.strip() and message.message_date and message.is_replyable)


def _build_checkpoint(
    previous_checkpoint: dict[str, object],
    messages: list[TelegramCollectedMessage],
) -> dict[str, object]:
    if not messages:
        return {
            "from_tg_message_id_exclusive": previous_checkpoint.get("through_tg_message_id_inclusive"),
            "through_tg_message_id_inclusive": previous_checkpoint.get("through_tg_message_id_inclusive"),
            "from_message_date_exclusive": previous_checkpoint.get("through_message_date_inclusive"),
            "through_message_date_inclusive": previous_checkpoint.get("through_message_date_inclusive"),
        }
    first = min(messages, key=lambda item: (item.message_date, item.tg_message_id))
    last = max(messages, key=lambda item: (item.message_date, item.tg_message_id))
    return {
        "from_tg_message_id_exclusive": previous_checkpoint.get("through_tg_message_id_inclusive"),
        "through_tg_message_id_inclusive": last.tg_message_id,
        "from_message_date_exclusive": previous_checkpoint.get("through_message_date_inclusive"),
        "through_message_date_inclusive": _ensure_aware_utc(last.message_date).isoformat(),
        "first_new_tg_message_id": first.tg_message_id,
        "first_new_message_date": _ensure_aware_utc(first.message_date).isoformat(),
    }


async def _add_stored_message(
    session: AsyncSession,
    *,
    community: Community,
    message: TelegramCollectedMessage,
    now: datetime,
) -> None:
    existing = await session.scalar(
        select(Message).where(
            Message.community_id == community.id,
            Message.tg_message_id == message.tg_message_id,
        )
    )
    if existing is not None:
        return
    session.add(
        Message(
            id=uuid.uuid4(),
            tg_message_id=message.tg_message_id,
            community_id=community.id,
            sender_user_id=message.sender.tg_user_id if message.sender else None,
            message_type=message.message_type,
            text=message.text,
            has_forward=message.has_forward,
            forward_from_id=message.forward_from_id,
            reply_to_message_id=message.reply_to_tg_message_id,
            views=message.views,
            reactions_count=message.reactions_count,
            collected_at=now,
            message_date=_ensure_aware_utc(message.message_date),
        )
    )


async def _upsert_active_member(
    session: AsyncSession,
    *,
    community_id: UUID,
    sender: TelegramCollectedUser,
    now: datetime,
) -> None:
    user = await session.scalar(select(User).where(User.tg_user_id == sender.tg_user_id))
    if user is None:
        user = User(
            id=uuid.uuid4(),
            tg_user_id=sender.tg_user_id,
            username=sender.username,
            first_name=sender.first_name,
            first_seen_at=now,
            last_updated_at=now,
        )
        session.add(user)
        await session.flush()
    else:
        if sender.username is not None:
            user.username = sender.username
        if sender.first_name is not None:
            user.first_name = sender.first_name
        user.last_updated_at = now

    member = await session.scalar(
        select(CommunityMember).where(
            CommunityMember.community_id == community_id,
            CommunityMember.user_id == user.id,
        )
    )
    if member is None:
        session.add(
            CommunityMember(
                id=uuid.uuid4(),
                community_id=community_id,
                user_id=user.id,
                activity_status=ActivityStatus.ACTIVE.value,
                event_count=1,
                last_active_at=now,
                first_seen_at=now,
                last_updated_at=now,
            )
        )
    else:
        member.activity_status = ActivityStatus.ACTIVE.value
        member.event_count += 1
        member.last_active_at = now
        member.last_updated_at = now


def _should_enqueue_detection(
    *,
    reason: str,
    detection_messages: int,
    settings_mode: str,
    has_detect_permission: bool,
    now: datetime,
    quiet_hours_start: time | None,
    quiet_hours_end: time | None,
) -> bool:
    return (
        reason == "engagement"
        and detection_messages > 0
        and settings_mode in ENABLED_DETECTION_MODES
        and has_detect_permission
        and not _is_quiet_time(
            now,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
        )
    )


def _update_community_metadata(
    community: Community,
    metadata: TelegramCollectionMetadata | None,
    *,
    now: datetime,
) -> None:
    if metadata is None:
        return
    if metadata.username is not None:
        community.username = metadata.username
    if metadata.title is not None:
        community.title = metadata.title
    if metadata.description is not None:
        community.description = metadata.description
    if metadata.member_count is not None:
        community.member_count = metadata.member_count
    if metadata.is_group is not None:
        community.is_group = metadata.is_group
    if metadata.is_broadcast is not None:
        community.is_broadcast = metadata.is_broadcast
    community.last_snapshot_at = now


def _unique_senders(messages: list[TelegramCollectedMessage]) -> list[TelegramCollectedUser]:
    unique: dict[int, TelegramCollectedUser] = {}
    for message in messages:
        if message.sender is not None:
            unique[message.sender.tg_user_id] = message.sender
    return list(unique.values())


def _overlap_checkpoint(value: object) -> int | None:
    checkpoint = _optional_int(value)
    if checkpoint is None:
        return None
    return max(checkpoint - CHECKPOINT_OVERLAP, 0)


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _truncate(value: str | None, limit: int) -> str:
    if value is None:
        return ""
    return " ".join(value.split())[:limit]


def _is_quiet_time(
    now: datetime,
    *,
    quiet_hours_start: time | None,
    quiet_hours_end: time | None,
) -> bool:
    if quiet_hours_start is None or quiet_hours_end is None:
        return False
    current_time = _ensure_aware_utc(now).time().replace(tzinfo=None)
    if quiet_hours_start == quiet_hours_end:
        return True
    if quiet_hours_start < quiet_hours_end:
        return quiet_hours_start <= current_time < quiet_hours_end
    return current_time >= quiet_hours_start or current_time < quiet_hours_end


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "CollectionAccountBanned",
    "CollectionAccountRateLimited",
    "CollectionCommunityInaccessible",
    "CollectionCommunityNotFound",
    "CollectionJobSummary",
    "TelegramCollectedMessage",
    "TelegramCollectedUser",
    "TelegramCollectionBatch",
    "TelegramCollectionMetadata",
    "TelegramEngagementCollector",
    "collect_community_engagement_messages",
    "record_collection_failure",
]
