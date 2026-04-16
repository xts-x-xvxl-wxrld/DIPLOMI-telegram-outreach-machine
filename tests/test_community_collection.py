from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from backend.db.enums import ActivityStatus, AnalysisStatus, CollectionRunStatus
from backend.db.models import CollectionRun, Community, CommunityMember, CommunitySnapshot, User
from backend.services.community_collection import (
    TelegramCollectedCommunity,
    TelegramCommunityCollection,
    TelegramMemberInfo,
    persist_community_collection,
    record_collection_failure,
)


@pytest.mark.asyncio
async def test_persist_collection_upserts_members_without_resetting_activity() -> None:
    community = Community(
        id=uuid4(),
        tg_id=100,
        username="seed_group",
        title="Old Title",
        status="candidate",
        store_messages=False,
    )
    existing_user = User(
        id=uuid4(),
        tg_user_id=1,
        username="oldname",
        first_name="Old",
    )
    existing_member = CommunityMember(
        id=uuid4(),
        community_id=community.id,
        user_id=existing_user.id,
        activity_status=ActivityStatus.ACTIVE.value,
        event_count=9,
    )
    repository = FakeCollectionRepository(
        communities=[community],
        users=[existing_user],
        members=[existing_member],
    )
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)

    summary = await persist_community_collection(
        repository,
        community=community,
        collected=TelegramCommunityCollection(
            community=TelegramCollectedCommunity(
                tg_id=100,
                username="seed_group",
                title="Seed Group",
                description="Research community",
                member_count=200,
                is_group=True,
                is_broadcast=False,
            ),
            members=[
                TelegramMemberInfo(tg_user_id=1, username="newname", first_name="New"),
                TelegramMemberInfo(tg_user_id=2, username=None, first_name="Second"),
                TelegramMemberInfo(tg_user_id=2, username="second", first_name="Second"),
            ],
            member_limit_reached=True,
            collection_notes=["capped at limit"],
        ),
        window_days=90,
        now=now,
    )

    assert summary.status == CollectionRunStatus.COMPLETED.value
    assert summary.members_seen == 2
    assert community.title == "Seed Group"
    assert community.member_count == 200
    assert community.last_snapshot_at == now
    assert len(repository.snapshots) == 1
    assert len(repository.collection_runs) == 1
    assert repository.collection_runs[0].analysis_status == AnalysisStatus.SKIPPED.value
    assert existing_user.username == "newname"
    assert existing_member.activity_status == ActivityStatus.ACTIVE.value
    assert existing_member.event_count == 9
    assert len(repository.users) == 2
    assert len(repository.members) == 2
    assert repository.members[1].activity_status == ActivityStatus.INACTIVE.value


@pytest.mark.asyncio
async def test_record_collection_failure_writes_failed_run() -> None:
    community = Community(id=uuid4(), tg_id=100, status="candidate", store_messages=False)
    repository = FakeCollectionRepository(communities=[community])

    summary = await record_collection_failure(
        repository,
        community_id=community.id,
        window_days=30,
        error_message="community inaccessible",
    )

    assert summary is not None
    assert summary.status == CollectionRunStatus.FAILED.value
    assert len(repository.collection_runs) == 1
    assert repository.collection_runs[0].status == CollectionRunStatus.FAILED.value
    assert repository.collection_runs[0].analysis_status == AnalysisStatus.SKIPPED.value
    assert repository.collection_runs[0].error_message == "community inaccessible"


class FakeCollectionRepository:
    def __init__(
        self,
        *,
        communities: list[Community],
        users: list[User] | None = None,
        members: list[CommunityMember] | None = None,
    ) -> None:
        self.communities = communities
        self.users = users or []
        self.members = members or []
        self.snapshots: list[CommunitySnapshot] = []
        self.collection_runs: list[CollectionRun] = []
        self.flush_count = 0

    async def get_community(self, community_id: UUID) -> Community | None:
        for community in self.communities:
            if community.id == community_id:
                return community
        return None

    async def get_user_by_tg_user_id(self, tg_user_id: int) -> User | None:
        for user in self.users:
            if user.tg_user_id == tg_user_id:
                return user
        return None

    async def add_user(self, user: User) -> None:
        self.users.append(user)

    async def get_community_member(self, community_id: UUID, user_id: UUID) -> CommunityMember | None:
        for member in self.members:
            if member.community_id == community_id and member.user_id == user_id:
                return member
        return None

    async def add_community_member(self, community_member: CommunityMember) -> None:
        self.members.append(community_member)

    async def add_snapshot(self, snapshot: CommunitySnapshot) -> None:
        self.snapshots.append(snapshot)

    async def add_collection_run(self, collection_run: CollectionRun) -> None:
        self.collection_runs.append(collection_run)

    async def flush(self) -> None:
        self.flush_count += 1
