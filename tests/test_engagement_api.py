from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.deps import settings_dep
from backend.api.routes.engagement import (
    get_community_engagement_settings,
    patch_engagement_topic,
    post_engagement_topic,
    put_community_engagement_settings,
)
from backend.api.schemas import (
    EngagementSettingsUpdate,
    EngagementTopicCreate,
    EngagementTopicUpdate,
)
from backend.db.enums import CommunityStatus, EngagementMode
from backend.db.models import Community, CommunityEngagementSettings, EngagementTopic


def test_engagement_routes_require_api_auth() -> None:
    app = create_app()
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace(bot_api_token="token")
    client = TestClient(app)

    response = client.get("/api/engagement/topics")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_engagement_settings_returns_disabled_default() -> None:
    community_id = uuid4()
    db = FakeDb(
        community=Community(
            id=community_id,
            tg_id=100,
            status=CommunityStatus.CANDIDATE.value,
            store_messages=False,
        )
    )

    response = await get_community_engagement_settings(community_id, db)  # type: ignore[arg-type]

    assert response.mode == "disabled"
    assert response.allow_join is False
    assert response.allow_post is False
    assert response.require_approval is True
    assert response.created_at is None
    assert db.added == []


@pytest.mark.asyncio
async def test_put_engagement_settings_forces_disabled_to_read_only() -> None:
    community_id = uuid4()
    db = FakeDb(
        community=Community(
            id=community_id,
            tg_id=100,
            status=CommunityStatus.MONITORING.value,
            store_messages=False,
        )
    )

    response = await put_community_engagement_settings(
        community_id,
        EngagementSettingsUpdate(
            mode=EngagementMode.DISABLED,
            allow_join=True,
            allow_post=True,
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.mode == "disabled"
    assert response.allow_join is False
    assert response.allow_post is False
    assert response.reply_only is True
    assert db.commits == 1
    assert isinstance(db.added[0], CommunityEngagementSettings)


@pytest.mark.asyncio
async def test_put_engagement_settings_rejects_auto_limited() -> None:
    community_id = uuid4()
    db = FakeDb(
        community=Community(
            id=community_id,
            tg_id=100,
            status=CommunityStatus.MONITORING.value,
            store_messages=False,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await put_community_engagement_settings(
            community_id,
            EngagementSettingsUpdate(mode=EngagementMode.AUTO_LIMITED),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "auto_limited_not_enabled"
    assert db.commits == 0


@pytest.mark.asyncio
async def test_put_engagement_settings_requires_approved_community_for_join() -> None:
    community_id = uuid4()
    db = FakeDb(
        community=Community(
            id=community_id,
            tg_id=100,
            status=CommunityStatus.CANDIDATE.value,
            store_messages=False,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await put_community_engagement_settings(
            community_id,
            EngagementSettingsUpdate(mode=EngagementMode.SUGGEST, allow_join=True),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "community_not_engagement_approved"


@pytest.mark.asyncio
async def test_create_topic_normalizes_keywords_and_returns_guidance_fields() -> None:
    db = FakeDb()

    response = await post_engagement_topic(
        EngagementTopicCreate(
            name=" Open-source CRM ",
            description=" Helpful CRM tradeoffs ",
            stance_guidance=" Be factual and non-salesy. ",
            trigger_keywords=[" CRM ", "crm", "Open Source"],
            negative_keywords=[" Jobs "],
            example_good_replies=[" Compare support models. "],
            example_bad_replies=[" Buy now. "],
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.name == "Open-source CRM"
    assert response.description == "Helpful CRM tradeoffs"
    assert response.stance_guidance == "Be factual and non-salesy."
    assert response.trigger_keywords == ["crm", "open source"]
    assert response.negative_keywords == ["jobs"]
    assert response.example_good_replies == ["Compare support models."]
    assert response.example_bad_replies == ["Buy now."]
    assert db.commits == 1


@pytest.mark.asyncio
async def test_create_active_topic_requires_trigger_keyword() -> None:
    db = FakeDb()

    with pytest.raises(HTTPException) as exc_info:
        await post_engagement_topic(
            EngagementTopicCreate(
                name="CRM",
                stance_guidance="Be useful.",
                trigger_keywords=[],
            ),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "topic_requires_trigger_keyword"
    assert db.commits == 0


@pytest.mark.asyncio
async def test_update_topic_rejects_unsafe_guidance() -> None:
    topic_id = uuid4()
    db = FakeDb(
        topic=EngagementTopic(
            id=topic_id,
            name="CRM",
            stance_guidance="Be useful.",
            trigger_keywords=["crm"],
            negative_keywords=[],
            example_good_replies=[],
            example_bad_replies=[],
            active=True,
            created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await patch_engagement_topic(
            topic_id,
            EngagementTopicUpdate(stance_guidance="Create fake consensus."),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "unsafe_topic_guidance"


class FakeDb:
    def __init__(
        self,
        *,
        community: Community | None = None,
        settings: CommunityEngagementSettings | None = None,
        topic: EngagementTopic | None = None,
        scalar_result: object | None = None,
    ) -> None:
        self.community = community
        self.settings = settings
        self.topic = topic
        self.scalar_result = scalar_result
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0

    async def get(self, model: object, item_id: object) -> object | None:
        if model is Community:
            return self.community
        if model is EngagementTopic:
            return self.topic
        return None

    async def scalar(self, statement: object) -> object | None:
        if self.scalar_result is not None:
            return self.scalar_result
        return self.settings

    def add(self, model: object) -> None:
        self.added.append(model)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1
