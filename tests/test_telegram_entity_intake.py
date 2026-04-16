from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.db.enums import (
    CommunitySource,
    CommunityStatus,
    TelegramEntityIntakeStatus,
    TelegramEntityType,
)
from backend.db.models import Community, TelegramEntityIntake, User
from backend.services.telegram_entity_intake import (
    TelegramEntityInfo,
    TelegramEntityResolveOutcome,
    resolve_telegram_entity_intake,
)


@pytest.mark.asyncio
async def test_resolve_channel_saves_candidate_community_and_links_intake() -> None:
    intake = _intake(username="example_channel")
    repository = FakeTelegramEntityIntakeRepository(intake=intake)
    resolver = FakeResolver(
        {
            "example_channel": TelegramEntityResolveOutcome.resolved(
                TelegramEntityInfo(
                    entity_type=TelegramEntityType.CHANNEL,
                    tg_id=12345,
                    username="example_channel",
                    title="Example Channel",
                    description="A public channel",
                    member_count=500,
                    is_group=False,
                    is_broadcast=True,
                )
            )
        }
    )

    summary = await resolve_telegram_entity_intake(
        repository,
        intake_id=intake.id,
        resolver=resolver,
    )

    assert summary.status == TelegramEntityIntakeStatus.RESOLVED.value
    assert summary.entity_type == TelegramEntityType.CHANNEL.value
    assert summary.community_id == repository.communities[0].id
    assert intake.status == TelegramEntityIntakeStatus.RESOLVED.value
    assert intake.community_id == repository.communities[0].id
    assert repository.communities[0].status == CommunityStatus.CANDIDATE.value
    assert repository.communities[0].source == CommunitySource.MANUAL.value
    assert repository.communities[0].match_reason == (
        "Direct Telegram handle intake: https://t.me/example_channel"
    )


@pytest.mark.asyncio
async def test_resolve_user_saves_user_and_links_intake_without_community() -> None:
    intake = _intake(username="public_user")
    repository = FakeTelegramEntityIntakeRepository(intake=intake)
    resolver = FakeResolver(
        {
            "public_user": TelegramEntityResolveOutcome.resolved(
                TelegramEntityInfo(
                    entity_type=TelegramEntityType.USER,
                    tg_id=777,
                    username="public_user",
                    first_name="Public",
                )
            )
        }
    )

    summary = await resolve_telegram_entity_intake(
        repository,
        intake_id=intake.id,
        resolver=resolver,
    )

    assert summary.status == TelegramEntityIntakeStatus.RESOLVED.value
    assert summary.entity_type == TelegramEntityType.USER.value
    assert summary.user_id == repository.users[0].id
    assert intake.user_id == repository.users[0].id
    assert intake.community_id is None
    assert repository.users[0].tg_user_id == 777
    assert repository.users[0].username == "public_user"
    assert repository.communities == []


@pytest.mark.asyncio
async def test_inaccessible_target_updates_intake_without_saving_entity() -> None:
    intake = _intake(username="privateish")
    repository = FakeTelegramEntityIntakeRepository(intake=intake)
    resolver = FakeResolver(
        {"privateish": TelegramEntityResolveOutcome.inaccessible("Target is private")}
    )

    summary = await resolve_telegram_entity_intake(
        repository,
        intake_id=intake.id,
        resolver=resolver,
    )

    assert summary.status == TelegramEntityIntakeStatus.INACCESSIBLE.value
    assert intake.status == TelegramEntityIntakeStatus.INACCESSIBLE.value
    assert intake.error_message == "Target is private"
    assert repository.users == []
    assert repository.communities == []


class FakeResolver:
    def __init__(self, outcomes: dict[str, TelegramEntityResolveOutcome]) -> None:
        self.outcomes = outcomes

    async def resolve_entity(self, username: str) -> TelegramEntityResolveOutcome:
        return self.outcomes[username]


class FakeTelegramEntityIntakeRepository:
    def __init__(
        self,
        *,
        intake: TelegramEntityIntake,
        communities: list[Community] | None = None,
        users: list[User] | None = None,
    ) -> None:
        self.intake = intake
        self.communities = communities or []
        self.users = users or []
        self.flush_count = 0

    async def get_intake(self, intake_id: UUID) -> TelegramEntityIntake | None:
        if intake_id == self.intake.id:
            return self.intake
        return None

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        for community in self.communities:
            if community.tg_id == tg_id:
                return community
        return None

    async def add_community(self, community: Community) -> None:
        self.communities.append(community)

    async def get_user_by_tg_user_id(self, tg_user_id: int) -> User | None:
        for user in self.users:
            if user.tg_user_id == tg_user_id:
                return user
        return None

    async def add_user(self, user: User) -> None:
        self.users.append(user)

    async def flush(self) -> None:
        self.flush_count += 1


def _intake(*, username: str) -> TelegramEntityIntake:
    return TelegramEntityIntake(
        id=uuid4(),
        raw_value=f"@{username}",
        normalized_key=f"username:{username}",
        username=username,
        telegram_url=f"https://t.me/{username}",
        status=TelegramEntityIntakeStatus.PENDING.value,
    )
