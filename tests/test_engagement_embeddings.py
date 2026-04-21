from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.db.models import EngagementMessageEmbedding, EngagementTopic
from backend.services import engagement_embeddings
from backend.services.engagement_embeddings import (
    EngagementEmbeddingError,
    build_message_embedding_text,
    delete_expired_message_embeddings,
    get_or_create_message_embeddings,
    get_or_create_topic_embedding,
    message_embedding_cache_key,
    select_semantic_trigger_messages,
)


@pytest.mark.asyncio
async def test_get_or_create_topic_embedding_invalidates_cache_when_profile_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    topic = _topic()
    embed_calls: list[list[str]] = []

    async def fake_load(*_args, profile_text_hash: str, **_kwargs):
        for row in session.added:
            if getattr(row, "profile_text_hash", None) == profile_text_hash:
                return row
        return None

    async def fake_embed(texts: list[str], model: str, dimensions: int) -> list[list[float]]:
        assert model == "embed-small"
        assert dimensions == 2
        embed_calls.append(list(texts))
        return [[1.0, 0.0]]

    monkeypatch.setattr(engagement_embeddings, "_load_topic_embedding_row", fake_load)

    first = await get_or_create_topic_embedding(
        session,
        topic,
        model="embed-small",
        dimensions=2,
        embed_texts_fn=fake_embed,
    )
    second = await get_or_create_topic_embedding(
        session,
        topic,
        model="embed-small",
        dimensions=2,
        embed_texts_fn=fake_embed,
    )
    topic.description = "Updated semantic profile text."
    third = await get_or_create_topic_embedding(
        session,
        topic,
        model="embed-small",
        dimensions=2,
        embed_texts_fn=fake_embed,
    )

    assert first == [1.0, 0.0]
    assert second == [1.0, 0.0]
    assert third == [1.0, 0.0]
    assert len(embed_calls) == 2
    assert session.flushes == 2


@pytest.mark.asyncio
async def test_get_or_create_message_embeddings_reuses_identical_normalized_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    community_id = uuid4()
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    messages = [
        _message(101, " CRM migration help ", now),
        _message(102, "CRM   migration help", now),
    ]
    embed_calls: list[list[str]] = []

    async def fake_load(
        *_args,
        community_id: object,
        tg_message_id: int | None,
        source_text_hash: str,
        model: str,
        dimensions: int,
        **_kwargs,
    ):
        for row in session.added:
            if not isinstance(row, EngagementMessageEmbedding):
                continue
            if (
                row.community_id == community_id
                and row.tg_message_id == tg_message_id
                and row.source_text_hash == source_text_hash
                and row.model == model
                and row.dimensions == dimensions
            ):
                return row
        return None

    async def fake_embed(texts: list[str], model: str, dimensions: int) -> list[list[float]]:
        assert model == "embed-small"
        assert dimensions == 2
        embed_calls.append(list(texts))
        return [[0.8, 0.2] for _ in texts]

    monkeypatch.setattr(engagement_embeddings, "_load_message_embedding_row", fake_load)
    monkeypatch.setattr(engagement_embeddings, "_utcnow", lambda: now)

    first = await get_or_create_message_embeddings(
        session,
        community_id=community_id,
        messages=messages,
        model="embed-small",
        dimensions=2,
        retention_days=14,
        embed_texts_fn=fake_embed,
    )
    second = await get_or_create_message_embeddings(
        session,
        community_id=community_id,
        messages=messages,
        model="embed-small",
        dimensions=2,
        retention_days=14,
        embed_texts_fn=fake_embed,
    )

    assert len(embed_calls) == 1
    assert embed_calls[0] == ["CRM migration help"]
    assert len(first) == 2
    assert len(second) == 2
    assert len([row for row in session.added if isinstance(row, EngagementMessageEmbedding)]) == 2


def test_validate_embedding_vector_rejects_wrong_dimensions() -> None:
    with pytest.raises(EngagementEmbeddingError, match="expected dimensions 3"):
        engagement_embeddings._validate_embedding_vector(
            [0.1, 0.2],
            dimensions=3,
            label="test vector",
        )


@pytest.mark.asyncio
async def test_select_semantic_trigger_messages_orders_stably_and_respects_negative_keywords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    community_id = uuid4()
    topic = _topic()
    topic.negative_keywords = ["jobs"]
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    old_earlier = _message(10, "CRM migration planning", now - timedelta(minutes=35))
    old_later = _message(20, "CRM migration checklist", now - timedelta(minutes=30))
    too_new = _message(30, "CRM migration now", now - timedelta(minutes=5))
    excluded = _message(40, "CRM jobs and migration", now - timedelta(minutes=25))
    messages = [old_later, excluded, too_new, old_earlier]

    async def fake_topic_embedding(*_args, **_kwargs) -> list[float]:
        return [1.0, 0.0]

    async def fake_message_embeddings(*_args, community_id: object, messages: list[object], model: str, dimensions: int, **_kwargs):
        vectors: dict[str, list[float]] = {}
        for message in messages:
            source_text_hash = engagement_embeddings.embedding_text_hash(
                build_message_embedding_text(message)
            )
            vectors[
                message_embedding_cache_key(
                    community_id=community_id,
                    tg_message_id=message.tg_message_id,
                    source_text_hash=source_text_hash,
                    model=model,
                    dimensions=dimensions,
                )
            ] = [1.0, 0.0]
        return vectors

    monkeypatch.setattr(engagement_embeddings, "get_or_create_topic_embedding", fake_topic_embedding)
    monkeypatch.setattr(
        engagement_embeddings,
        "get_or_create_message_embeddings",
        fake_message_embeddings,
    )

    matches = await select_semantic_trigger_messages(
        FakeSession(),
        community_id=community_id,
        topic=topic,
        messages=messages,
        settings=SimpleNamespace(
            openai_embedding_model="embed-small",
            openai_embedding_dimensions=2,
            engagement_semantic_match_threshold=0.5,
            engagement_max_semantic_matches_per_topic=3,
            engagement_max_embedding_messages_per_run=10,
            engagement_message_embedding_retention_days=14,
        ),
        now=now,
    )

    assert [match.message.tg_message_id for match in matches] == [10, 20, 30]
    assert [match.rank for match in matches] == [1, 2, 3]
    assert all(match.similarity == pytest.approx(1.0) for match in matches)


def test_build_message_embedding_text_uses_only_public_text_and_reply_context() -> None:
    message = SimpleNamespace(
        tg_message_id=123,
        text="Call me at +1 555 123 4567 about CRM migration.",
        reply_context="Asked how to compare tools.",
        sender_username="private_user",
        sender_user_id=999,
        phone="+1 555 123 4567",
        message_date=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
    )

    rendered = build_message_embedding_text(message)

    assert "[phone redacted]" in rendered
    assert "private_user" not in rendered
    assert "999" not in rendered
    assert "Asked how to compare tools." in rendered


@pytest.mark.asyncio
async def test_delete_expired_message_embeddings_returns_deleted_count() -> None:
    session = FakeSession(rowcount=3)

    deleted = await delete_expired_message_embeddings(session)

    assert deleted == 3
    assert session.execute_calls == 1


class FakeSession:
    def __init__(self, *, rowcount: int = 0) -> None:
        self.added: list[object] = []
        self.flushes = 0
        self.execute_calls = 0
        self.rowcount = rowcount

    def add(self, model: object) -> None:
        self.added.append(model)

    async def flush(self) -> None:
        self.flushes += 1

    async def execute(self, _statement: object) -> SimpleNamespace:
        self.execute_calls += 1
        return SimpleNamespace(rowcount=self.rowcount)


def _topic() -> EngagementTopic:
    return EngagementTopic(
        id=uuid4(),
        name="Open-source CRM",
        description="People comparing CRM migration tradeoffs.",
        stance_guidance="Be practical and non-salesy.",
        trigger_keywords=[],
        negative_keywords=[],
        example_good_replies=["Compare export access, setup effort, and integrations."],
        example_bad_replies=[],
        active=True,
        created_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
    )


def _message(
    tg_message_id: int,
    text: str,
    message_date: datetime,
) -> SimpleNamespace:
    return SimpleNamespace(
        tg_message_id=tg_message_id,
        text=text,
        reply_context=None,
        message_date=message_date,
    )
