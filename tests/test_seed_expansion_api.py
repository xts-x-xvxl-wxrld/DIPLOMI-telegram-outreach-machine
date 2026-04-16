from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.api.routes.seeds import start_seed_group_expansion
from backend.api.schemas import SeedGroupExpansionJobRequest
from backend.db.models import SeedGroup
from backend.queue.client import QueuedJob


@pytest.mark.asyncio
async def test_seed_group_expansion_endpoint_enqueues_seed_expand(monkeypatch) -> None:
    seed_group_id = uuid4()
    brief_id = uuid4()
    db = FakeDb(seed_group=SeedGroup(id=seed_group_id, name="Seeds", normalized_name="seeds"), count=2)
    captured: dict[str, object] = {}

    def fake_enqueue_seed_expansion(*args: object, **kwargs: object) -> QueuedJob:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return QueuedJob(id="job-1", type="seed.expand")

    monkeypatch.setattr(
        "backend.api.routes.seeds.enqueue_seed_expansion",
        fake_enqueue_seed_expansion,
    )

    response = await start_seed_group_expansion(
        seed_group_id,
        SeedGroupExpansionJobRequest(brief_id=brief_id, depth=1),
        db,  # type: ignore[arg-type]
    )

    assert response.job.type == "seed.expand"
    assert captured["args"] == (seed_group_id, brief_id)
    assert captured["kwargs"] == {"depth": 1, "requested_by": "operator"}


@pytest.mark.asyncio
async def test_seed_group_expansion_endpoint_rejects_empty_resolved_group() -> None:
    seed_group_id = uuid4()
    db = FakeDb(seed_group=SeedGroup(id=seed_group_id, name="Seeds", normalized_name="seeds"), count=0)

    with pytest.raises(HTTPException) as exc_info:
        await start_seed_group_expansion(
            seed_group_id,
            SeedGroupExpansionJobRequest(brief_id=None, depth=1),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "no_resolved_seed_communities"


class FakeDb:
    def __init__(self, *, seed_group: SeedGroup | None, count: int) -> None:
        self.seed_group = seed_group
        self.count = count

    async def get(self, model: object, item_id: object) -> SeedGroup | None:
        return self.seed_group

    async def scalar(self, statement: object) -> int:
        return self.count
