from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.api.routes.engagement import post_engagement_target
from backend.api.schemas import EngagementTargetCreateRequest
from backend.db.enums import EngagementTargetRefType, EngagementTargetStatus
from backend.db.models import EngagementTarget


@pytest.mark.asyncio
async def test_duplicate_pending_engagement_target_without_loaded_community_creates_new_row() -> None:
    target = EngagementTarget(
        id=uuid4(),
        community_id=None,
        submitted_ref="username:example",
        submitted_ref_type=EngagementTargetRefType.TELEGRAM_USERNAME.value,
        status=EngagementTargetStatus.PENDING.value,
        allow_join=False,
        allow_detect=False,
        allow_post=False,
        added_by="telegram:123",
        created_at=_now(),
        updated_at=_now(),
    )
    db = _FakeDb(target)

    response = await post_engagement_target(
        EngagementTargetCreateRequest(target_ref="@example", added_by="telegram:123"),
        db,  # type: ignore[arg-type]
    )

    assert response.id != target.id
    assert response.community_id is None
    assert response.community_title is None
    assert len(db.added) == 1


class _FakeDb:
    def __init__(self, target: EngagementTarget) -> None:
        self.target = target
        self.added: list[object] = []
        self.commits = 0

    async def get(self, model: object, item_id: object) -> object | None:
        del model, item_id
        return None

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.target

    def add(self, model: object) -> None:
        self.added.append(model)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def _now() -> datetime:
    return datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc)
