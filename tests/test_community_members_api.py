from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.api.routes.communities import list_community_members
from backend.db.models import Community, CommunityMember, User


@pytest.mark.asyncio
async def test_list_community_members_returns_allowed_fields_only() -> None:
    community_id = uuid4()
    user = User(
        id=uuid4(),
        tg_user_id=12345,
        username="public_user",
        first_name="Public",
    )
    member = CommunityMember(
        id=uuid4(),
        community_id=community_id,
        user_id=user.id,
        activity_status="active",
        event_count=9,
        first_seen_at=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
        last_updated_at=datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc),
        last_active_at=datetime(2026, 4, 15, 10, 30, tzinfo=timezone.utc),
    )
    db = FakeDb(
        community=Community(id=community_id, tg_id=100, status="candidate", store_messages=False),
        rows=[(member, user)],
        total=1,
    )

    response = await list_community_members(
        community_id,
        db,  # type: ignore[arg-type]
        limit=20,
        offset=0,
    )

    assert response.total == 1
    assert response.items[0].tg_user_id == 12345
    assert response.items[0].username == "public_user"
    assert response.items[0].first_name == "Public"
    assert response.items[0].membership_status == "member"
    assert response.items[0].activity_status == "active"
    assert "event_count" not in response.items[0].model_dump()
    assert "phone" not in response.items[0].model_dump()


@pytest.mark.asyncio
async def test_list_community_members_rejects_bad_activity_status() -> None:
    community_id = uuid4()
    db = FakeDb(
        community=Community(id=community_id, tg_id=100, status="candidate", store_messages=False),
        rows=[],
        total=0,
    )

    with pytest.raises(HTTPException) as exc_info:
        await list_community_members(
            community_id,
            db,  # type: ignore[arg-type]
            activity_status="lurking",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "invalid_activity_status"


@pytest.mark.asyncio
async def test_list_community_members_rejects_conflicting_username_filters() -> None:
    community_id = uuid4()
    db = FakeDb(
        community=Community(id=community_id, tg_id=100, status="candidate", store_messages=False),
        rows=[],
        total=0,
    )

    with pytest.raises(HTTPException) as exc_info:
        await list_community_members(
            community_id,
            db,  # type: ignore[arg-type]
            username_present=True,
            has_public_username=False,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "conflicting_username_filters"


class FakeDb:
    def __init__(
        self,
        *,
        community: Community | None,
        rows: list[tuple[CommunityMember, User]],
        total: int,
    ) -> None:
        self.community = community
        self.rows = rows
        self.total = total

    async def get(self, model: object, item_id: object) -> Community | None:
        return self.community

    async def scalar(self, statement: object) -> int:
        return self.total

    async def execute(self, statement: object) -> "FakeResult":
        return FakeResult(self.rows)


class FakeResult:
    def __init__(self, rows: list[tuple[CommunityMember, User]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[CommunityMember, User]]:
        return self.rows
