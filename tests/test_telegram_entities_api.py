from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.api.routes.telegram_entities import create_telegram_entity_intake
from backend.api.schemas import TelegramEntityIntakeRequest
from backend.db.enums import TelegramEntityIntakeStatus
from backend.db.models import TelegramEntityIntake
from backend.queue.client import QueuedJob


@pytest.mark.asyncio
async def test_create_telegram_entity_intake_enqueues_resolution(monkeypatch) -> None:
    intake_id = uuid4()
    intake = TelegramEntityIntake(
        id=intake_id,
        raw_value="@example",
        normalized_key="username:example",
        username="example",
        telegram_url="https://t.me/example",
        status=TelegramEntityIntakeStatus.PENDING.value,
        requested_by="telegram_bot",
        created_at=datetime(2026, 4, 16, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 16, tzinfo=timezone.utc),
    )
    captured: dict[str, object] = {}

    async def fake_create_or_reset_intake(*args: object, **kwargs: object) -> TelegramEntityIntake:
        captured["create_args"] = args
        captured["create_kwargs"] = kwargs
        return intake

    def fake_enqueue(intake_id_arg: object, **kwargs: object) -> QueuedJob:
        captured["enqueue_args"] = (intake_id_arg,)
        captured["enqueue_kwargs"] = kwargs
        return QueuedJob(id="job-1", type="telegram_entity.resolve")

    monkeypatch.setattr(
        "backend.api.routes.telegram_entities.create_or_reset_intake",
        fake_create_or_reset_intake,
    )
    monkeypatch.setattr(
        "backend.api.routes.telegram_entities.enqueue_telegram_entity_resolve",
        fake_enqueue,
    )
    db = FakeDb()

    response = await create_telegram_entity_intake(
        TelegramEntityIntakeRequest(handle="@example", requested_by="telegram_bot"),
        db,  # type: ignore[arg-type]
    )

    assert response.intake.id == intake_id
    assert response.job.type == "telegram_entity.resolve"
    assert db.commits == 1
    assert captured["enqueue_args"] == (intake_id,)
    assert captured["enqueue_kwargs"] == {"requested_by": "telegram_bot"}


class FakeDb:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1
