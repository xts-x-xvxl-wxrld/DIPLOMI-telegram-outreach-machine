from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import (
    CommunitySource,
    CommunityStatus,
    TelegramEntityIntakeStatus,
    TelegramEntityType,
)
from backend.db.models import Community, TelegramEntityIntake, User
from backend.services.seed_import import normalize_telegram_seed
from backend.services.seed_resolution import TransientResolveError

EntityResolveStatus = Literal["resolved", "invalid", "inaccessible", "failed"]


class TelegramEntityIntakeError(RuntimeError):
    pass


class TelegramEntityIntakeNotFound(TelegramEntityIntakeError):
    pass


@dataclass(frozen=True)
class TelegramEntityInfo:
    entity_type: TelegramEntityType
    tg_id: int
    username: str | None
    title: str | None = None
    first_name: str | None = None
    description: str | None = None
    member_count: int | None = None
    is_group: bool | None = None
    is_broadcast: bool | None = None


@dataclass(frozen=True)
class TelegramEntityResolveOutcome:
    status: EntityResolveStatus
    entity: TelegramEntityInfo | None = None
    error_message: str | None = None

    @classmethod
    def resolved(cls, entity: TelegramEntityInfo) -> "TelegramEntityResolveOutcome":
        return cls(status=TelegramEntityIntakeStatus.RESOLVED.value, entity=entity)

    @classmethod
    def inaccessible(cls, message: str | None = None) -> "TelegramEntityResolveOutcome":
        return cls(status=TelegramEntityIntakeStatus.INACCESSIBLE.value, error_message=message)

    @classmethod
    def failed(cls, message: str | None = None) -> "TelegramEntityResolveOutcome":
        return cls(status=TelegramEntityIntakeStatus.FAILED.value, error_message=message)

    @classmethod
    def invalid(cls, message: str | None = None) -> "TelegramEntityResolveOutcome":
        return cls(status=TelegramEntityIntakeStatus.INVALID.value, error_message=message)


class TelegramEntityResolverAdapter(Protocol):
    async def resolve_entity(self, username: str) -> TelegramEntityResolveOutcome:
        pass


class TelegramEntityIntakeRepository(Protocol):
    async def get_intake(self, intake_id: UUID) -> TelegramEntityIntake | None:
        pass

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        pass

    async def add_community(self, community: Community) -> None:
        pass

    async def get_user_by_tg_user_id(self, tg_user_id: int) -> User | None:
        pass

    async def add_user(self, user: User) -> None:
        pass

    async def flush(self) -> None:
        pass


class SqlAlchemyTelegramEntityIntakeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_intake(self, intake_id: UUID) -> TelegramEntityIntake | None:
        return await self.session.get(TelegramEntityIntake, intake_id)

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        return await self.session.scalar(select(Community).where(Community.tg_id == tg_id))

    async def add_community(self, community: Community) -> None:
        self.session.add(community)

    async def get_user_by_tg_user_id(self, tg_user_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.tg_user_id == tg_user_id))

    async def add_user(self, user: User) -> None:
        self.session.add(user)

    async def flush(self) -> None:
        await self.session.flush()


@dataclass(frozen=True)
class TelegramEntityResolveSummary:
    intake_id: UUID
    status: str
    entity_type: str | None = None
    community_id: UUID | None = None
    user_id: UUID | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "job_type": "telegram_entity.resolve",
            "intake_id": str(self.intake_id),
            "entity_type": self.entity_type,
            "community_id": str(self.community_id) if self.community_id else None,
            "user_id": str(self.user_id) if self.user_id else None,
            "error_message": self.error_message,
        }


async def create_or_reset_intake(
    db: AsyncSession,
    raw_value: str,
    *,
    requested_by: str | None,
) -> TelegramEntityIntake:
    normalized = normalize_telegram_seed(raw_value)
    intake = await db.scalar(
        select(TelegramEntityIntake).where(
            TelegramEntityIntake.normalized_key == normalized.normalized_key
        )
    )
    now = datetime.now(timezone.utc)
    if intake is None:
        intake = TelegramEntityIntake(
            id=uuid.uuid4(),
            raw_value=normalized.raw_value,
            normalized_key=normalized.normalized_key,
            username=normalized.username,
            telegram_url=normalized.telegram_url,
            status=TelegramEntityIntakeStatus.PENDING.value,
            requested_by=requested_by,
            updated_at=now,
        )
        db.add(intake)
    else:
        intake.raw_value = normalized.raw_value
        intake.username = normalized.username
        intake.telegram_url = normalized.telegram_url
        intake.status = TelegramEntityIntakeStatus.PENDING.value
        intake.entity_type = None
        intake.community_id = None
        intake.user_id = None
        intake.error_message = None
        intake.requested_by = requested_by or intake.requested_by
        intake.updated_at = now
    await db.flush()
    return intake


async def resolve_telegram_entity_intake(
    repository: TelegramEntityIntakeRepository,
    *,
    intake_id: UUID,
    resolver: TelegramEntityResolverAdapter,
) -> TelegramEntityResolveSummary:
    intake = await repository.get_intake(intake_id)
    if intake is None:
        raise TelegramEntityIntakeNotFound(f"Telegram entity intake not found: {intake_id}")

    try:
        outcome = await resolver.resolve_entity(intake.username)
    except TransientResolveError as exc:
        outcome = TelegramEntityResolveOutcome.failed(str(exc))

    if outcome.status == TelegramEntityIntakeStatus.RESOLVED.value:
        if outcome.entity is None:
            outcome = TelegramEntityResolveOutcome.failed("Resolver returned no entity data")
        elif outcome.entity.entity_type in {
            TelegramEntityType.CHANNEL,
            TelegramEntityType.GROUP,
        }:
            community = await _upsert_direct_community(repository, intake, outcome.entity)
            _mark_resolved_intake(
                intake,
                entity_type=outcome.entity.entity_type.value,
                community_id=community.id,
                user_id=None,
            )
            await repository.flush()
            return TelegramEntityResolveSummary(
                intake_id=intake.id,
                status=TelegramEntityIntakeStatus.RESOLVED.value,
                entity_type=outcome.entity.entity_type.value,
                community_id=community.id,
            )
        else:
            user = await _upsert_direct_user(repository, outcome.entity)
            _mark_resolved_intake(
                intake,
                entity_type=outcome.entity.entity_type.value,
                community_id=None,
                user_id=user.id,
            )
            await repository.flush()
            return TelegramEntityResolveSummary(
                intake_id=intake.id,
                status=TelegramEntityIntakeStatus.RESOLVED.value,
                entity_type=outcome.entity.entity_type.value,
                user_id=user.id,
            )

    _mark_failed_intake(intake, status=outcome.status, error_message=outcome.error_message)
    await repository.flush()
    return TelegramEntityResolveSummary(
        intake_id=intake.id,
        status=outcome.status,
        error_message=outcome.error_message,
    )


async def _upsert_direct_community(
    repository: TelegramEntityIntakeRepository,
    intake: TelegramEntityIntake,
    resolved: TelegramEntityInfo,
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

    community.username = resolved.username or intake.username or community.username
    community.title = resolved.title or community.title
    if resolved.description is not None:
        community.description = resolved.description
    if resolved.member_count is not None:
        community.member_count = resolved.member_count
    community.is_group = bool(resolved.is_group)
    community.is_broadcast = bool(resolved.is_broadcast)
    community.source = CommunitySource.MANUAL.value
    community.match_reason = f"Direct Telegram handle intake: {intake.telegram_url}"
    if not community.status:
        community.status = CommunityStatus.CANDIDATE.value
    return community


async def _upsert_direct_user(
    repository: TelegramEntityIntakeRepository,
    resolved: TelegramEntityInfo,
) -> User:
    user = await repository.get_user_by_tg_user_id(resolved.tg_id)
    now = datetime.now(timezone.utc)
    if user is None:
        user = User(
            id=uuid.uuid4(),
            tg_user_id=resolved.tg_id,
            username=resolved.username,
            first_name=resolved.first_name or resolved.title,
            last_updated_at=now,
        )
        await repository.add_user(user)
        return user

    user.username = resolved.username or user.username
    user.first_name = resolved.first_name or resolved.title or user.first_name
    user.last_updated_at = now
    return user


def _mark_resolved_intake(
    intake: TelegramEntityIntake,
    *,
    entity_type: str,
    community_id: UUID | None,
    user_id: UUID | None,
) -> None:
    intake.status = TelegramEntityIntakeStatus.RESOLVED.value
    intake.entity_type = entity_type
    intake.community_id = community_id
    intake.user_id = user_id
    intake.error_message = None
    intake.updated_at = datetime.now(timezone.utc)


def _mark_failed_intake(
    intake: TelegramEntityIntake,
    *,
    status: str,
    error_message: str | None,
) -> None:
    intake.status = status
    intake.entity_type = None
    intake.community_id = None
    intake.user_id = None
    intake.error_message = error_message
    intake.updated_at = datetime.now(timezone.utc)
