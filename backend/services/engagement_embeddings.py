from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import get_settings
from backend.db.models import (
    EngagementMessageEmbedding,
    EngagementTopic,
    EngagementTopicEmbedding,
)

EmbeddingProvider = Callable[[Sequence[str], str, int], Awaitable[list[list[float]]]]

MAX_EMBEDDING_BATCH_SIZE = 100
SIMILARITY_ROUND_PLACES = 6
PREFERRED_AGE_MINUTES_MIN = 15
PREFERRED_AGE_MINUTES_MAX = 60
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")


class SupportsMessageEmbedding(Protocol):
    tg_message_id: int | None
    text: str
    reply_context: str | None
    message_date: datetime | None


class EngagementEmbeddingError(ValueError):
    pass


@dataclass(frozen=True)
class SemanticTriggerMatch:
    message: SupportsMessageEmbedding
    similarity: float
    threshold: float
    rank: int
    embedding_model: str
    embedding_dimensions: int
    source_text_hash: str


@dataclass(frozen=True)
class PreparedMessageEmbedding:
    message: SupportsMessageEmbedding
    normalized_text: str
    source_text_hash: str
    cache_key: str


def normalize_embedding_text(value: str) -> str:
    cleaned = " ".join((value or "").strip().split())
    if not cleaned:
        return ""
    return PHONE_RE.sub("[phone redacted]", cleaned)


def embedding_text_hash(value: str) -> str:
    normalized = normalize_embedding_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_topic_profile_text(topic: EngagementTopic) -> str:
    parts: list[str] = [f"Topic: {topic.name}", f"Stance guidance: {topic.stance_guidance}"]
    if topic.description:
        parts.append(f"Description: {topic.description}")
    if topic.example_good_replies:
        examples = "\n".join(f"- {example}" for example in topic.example_good_replies if example)
        if examples:
            parts.append(f"Good reply examples:\n{examples}")
    return normalize_embedding_text("\n\n".join(parts))


def build_message_embedding_text(message: SupportsMessageEmbedding) -> str:
    parts = [message.text]
    if message.reply_context:
        parts.append(f"Reply context: {message.reply_context}")
    return normalize_embedding_text("\n\n".join(part for part in parts if part))


def message_embedding_cache_key(
    *,
    community_id: UUID,
    tg_message_id: int | None,
    source_text_hash: str,
    model: str,
    dimensions: int,
) -> str:
    message_part = str(tg_message_id) if tg_message_id is not None else "none"
    return "|".join((str(community_id), message_part, source_text_hash, model, str(dimensions)))


async def request_embeddings(
    texts: Sequence[str],
    model: str,
    dimensions: int,
) -> list[list[float]]:
    if not texts:
        return []

    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError("openai must be installed before embedding matching can run") from exc

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for engagement embedding matching")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=model,
        input=list(texts),
        dimensions=dimensions,
    )
    return [list(item.embedding) for item in response.data]


async def get_or_create_topic_embedding(
    db: AsyncSession,
    topic: EngagementTopic,
    *,
    model: str,
    dimensions: int,
    embed_texts_fn: EmbeddingProvider = request_embeddings,
) -> list[float]:
    profile_text = build_topic_profile_text(topic)
    if not profile_text:
        raise EngagementEmbeddingError("Topic requires semantic profile text before embedding")

    profile_text_hash = embedding_text_hash(profile_text)
    cached = await _load_topic_embedding_row(
        db,
        topic_id=topic.id,
        model=model,
        dimensions=dimensions,
        profile_text_hash=profile_text_hash,
    )
    if cached is not None:
        return _validate_embedding_vector(cached.embedding, dimensions=dimensions, label="topic embedding cache")

    vectors = await _embed_texts_batched(
        [profile_text],
        model=model,
        dimensions=dimensions,
        embed_texts_fn=embed_texts_fn,
    )
    vector = _validate_embedding_vector(vectors[0], dimensions=dimensions, label="topic embedding response")
    row = EngagementTopicEmbedding(
        id=uuid.uuid4(),
        topic_id=topic.id,
        model=model,
        dimensions=dimensions,
        profile_text_hash=profile_text_hash,
        embedding=vector,
        created_at=_utcnow(),
    )
    db.add(row)
    await db.flush()
    return vector


async def get_or_create_message_embeddings(
    db: AsyncSession,
    *,
    community_id: UUID,
    messages: Sequence[SupportsMessageEmbedding],
    model: str,
    dimensions: int,
    retention_days: int,
    embed_texts_fn: EmbeddingProvider = request_embeddings,
) -> dict[str, list[float]]:
    if retention_days <= 0:
        raise EngagementEmbeddingError("Message embedding retention_days must be positive")

    prepared = _prepare_message_embeddings(
        community_id=community_id,
        messages=messages,
        model=model,
        dimensions=dimensions,
    )
    if not prepared:
        return {}

    now = _utcnow()
    expires_at = now + timedelta(days=retention_days)
    vectors_by_key: dict[str, list[float]] = {}
    missing_by_text: dict[str, list[PreparedMessageEmbedding]] = {}

    for item in prepared:
        cached = await _load_message_embedding_row(
            db,
            community_id=community_id,
            tg_message_id=item.message.tg_message_id,
            source_text_hash=item.source_text_hash,
            model=model,
            dimensions=dimensions,
        )
        if cached is not None and _ensure_aware_utc(cached.expires_at) > now:
            vectors_by_key[item.cache_key] = _validate_embedding_vector(
                cached.embedding,
                dimensions=dimensions,
                label="message embedding cache",
            )
            continue
        missing_by_text.setdefault(item.normalized_text, []).append(item)

    if missing_by_text:
        missing_texts = list(missing_by_text.keys())
        response_vectors = await _embed_texts_batched(
            missing_texts,
            model=model,
            dimensions=dimensions,
            embed_texts_fn=embed_texts_fn,
        )
        for normalized_text, vector in zip(missing_texts, response_vectors, strict=True):
            validated = _validate_embedding_vector(
                vector,
                dimensions=dimensions,
                label="message embedding response",
            )
            for item in missing_by_text[normalized_text]:
                row = EngagementMessageEmbedding(
                    id=uuid.uuid4(),
                    community_id=community_id,
                    tg_message_id=item.message.tg_message_id,
                    source_text_hash=item.source_text_hash,
                    model=model,
                    dimensions=dimensions,
                    embedding=validated,
                    expires_at=expires_at,
                    created_at=now,
                )
                db.add(row)
                vectors_by_key[item.cache_key] = validated
        await db.flush()

    return vectors_by_key


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise EngagementEmbeddingError("Embedding vectors must have the same dimensions")

    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(l_value * r_value for l_value, r_value in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )


async def select_semantic_trigger_messages(
    db: AsyncSession,
    *,
    community_id: UUID,
    topic: EngagementTopic,
    messages: Sequence[SupportsMessageEmbedding],
    settings: object,
    now: datetime | None = None,
    embed_texts_fn: EmbeddingProvider = request_embeddings,
) -> list[SemanticTriggerMatch]:
    threshold = float(getattr(settings, "engagement_semantic_match_threshold"))
    max_matches = max(int(getattr(settings, "engagement_max_semantic_matches_per_topic")), 0)
    max_messages = max(int(getattr(settings, "engagement_max_embedding_messages_per_run")), 0)
    model = str(getattr(settings, "openai_embedding_model"))
    dimensions = int(getattr(settings, "openai_embedding_dimensions"))
    retention_days = int(getattr(settings, "engagement_message_embedding_retention_days"))

    if max_matches == 0 or max_messages == 0:
        return []

    eligible_messages = [
        message
        for message in list(messages)[:max_messages]
        if build_message_embedding_text(message)
        and not _message_matches_negative_keyword(topic, message)
    ]
    if not eligible_messages:
        return []

    topic_embedding = await get_or_create_topic_embedding(
        db,
        topic,
        model=model,
        dimensions=dimensions,
        embed_texts_fn=embed_texts_fn,
    )
    message_embeddings = await get_or_create_message_embeddings(
        db,
        community_id=community_id,
        messages=eligible_messages,
        model=model,
        dimensions=dimensions,
        retention_days=retention_days,
        embed_texts_fn=embed_texts_fn,
    )
    effective_now = _ensure_aware_utc(now) if now is not None else _utcnow()

    matches: list[SemanticTriggerMatch] = []
    for message in eligible_messages:
        source_text_hash = embedding_text_hash(build_message_embedding_text(message))
        cache_key = message_embedding_cache_key(
            community_id=community_id,
            tg_message_id=message.tg_message_id,
            source_text_hash=source_text_hash,
            model=model,
            dimensions=dimensions,
        )
        vector = message_embeddings.get(cache_key)
        if vector is None:
            continue
        similarity = cosine_similarity(topic_embedding, vector)
        if similarity < threshold:
            continue
        matches.append(
            SemanticTriggerMatch(
                message=message,
                similarity=similarity,
                threshold=threshold,
                rank=0,
                embedding_model=model,
                embedding_dimensions=dimensions,
                source_text_hash=source_text_hash,
            )
        )

    matches.sort(key=lambda item: _semantic_match_sort_key(item, now=effective_now))
    ranked = matches[:max_matches]
    return [replace(match, rank=index) for index, match in enumerate(ranked, start=1)]


async def delete_expired_message_embeddings(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    effective_now = _ensure_aware_utc(now) if now is not None else _utcnow()
    result = await db.execute(
        delete(EngagementMessageEmbedding).where(
            EngagementMessageEmbedding.expires_at <= effective_now
        )
    )
    return int(result.rowcount or 0)


async def _load_topic_embedding_row(
    db: AsyncSession,
    *,
    topic_id: UUID,
    model: str,
    dimensions: int,
    profile_text_hash: str,
) -> EngagementTopicEmbedding | None:
    return await db.scalar(
        select(EngagementTopicEmbedding)
        .where(
            EngagementTopicEmbedding.topic_id == topic_id,
            EngagementTopicEmbedding.model == model,
            EngagementTopicEmbedding.dimensions == dimensions,
            EngagementTopicEmbedding.profile_text_hash == profile_text_hash,
        )
        .limit(1)
    )


async def _load_message_embedding_row(
    db: AsyncSession,
    *,
    community_id: UUID,
    tg_message_id: int | None,
    source_text_hash: str,
    model: str,
    dimensions: int,
) -> EngagementMessageEmbedding | None:
    query = select(EngagementMessageEmbedding).where(
        EngagementMessageEmbedding.community_id == community_id,
        EngagementMessageEmbedding.source_text_hash == source_text_hash,
        EngagementMessageEmbedding.model == model,
        EngagementMessageEmbedding.dimensions == dimensions,
    )
    if tg_message_id is None:
        query = query.where(EngagementMessageEmbedding.tg_message_id.is_(None))
    else:
        query = query.where(EngagementMessageEmbedding.tg_message_id == tg_message_id)
    return await db.scalar(query.order_by(EngagementMessageEmbedding.created_at.desc()).limit(1))


async def _embed_texts_batched(
    texts: Sequence[str],
    *,
    model: str,
    dimensions: int,
    embed_texts_fn: EmbeddingProvider,
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for chunk in _chunked(texts, MAX_EMBEDDING_BATCH_SIZE):
        vectors.extend(await embed_texts_fn(chunk, model, dimensions))
    if len(vectors) != len(texts):
        raise EngagementEmbeddingError("Embedding provider returned an unexpected vector count")
    return vectors


def _prepare_message_embeddings(
    *,
    community_id: UUID,
    messages: Sequence[SupportsMessageEmbedding],
    model: str,
    dimensions: int,
) -> list[PreparedMessageEmbedding]:
    prepared: list[PreparedMessageEmbedding] = []
    for message in messages:
        normalized_text = build_message_embedding_text(message)
        if not normalized_text:
            continue
        source_text_hash = embedding_text_hash(normalized_text)
        prepared.append(
            PreparedMessageEmbedding(
                message=message,
                normalized_text=normalized_text,
                source_text_hash=source_text_hash,
                cache_key=message_embedding_cache_key(
                    community_id=community_id,
                    tg_message_id=message.tg_message_id,
                    source_text_hash=source_text_hash,
                    model=model,
                    dimensions=dimensions,
                ),
            )
        )
    return prepared


def _message_matches_negative_keyword(
    topic: EngagementTopic,
    message: SupportsMessageEmbedding,
) -> bool:
    normalized_text = build_message_embedding_text(message).casefold()
    return any(
        keyword.casefold() in normalized_text
        for keyword in list(topic.negative_keywords or [])
        if keyword
    )


def _semantic_match_sort_key(
    match: SemanticTriggerMatch,
    *,
    now: datetime,
) -> tuple[float, float, datetime, int]:
    message_date = _sortable_datetime(match.message.message_date)
    return (
        -round(match.similarity, SIMILARITY_ROUND_PLACES),
        _age_fit_penalty(message_date, now=now),
        message_date,
        match.message.tg_message_id if match.message.tg_message_id is not None else -1,
    )


def _age_fit_penalty(message_date: datetime, *, now: datetime) -> float:
    age_minutes = max((now - message_date).total_seconds() / 60.0, 0.0)
    if PREFERRED_AGE_MINUTES_MIN <= age_minutes <= PREFERRED_AGE_MINUTES_MAX:
        return 0.0
    if age_minutes < PREFERRED_AGE_MINUTES_MIN:
        return PREFERRED_AGE_MINUTES_MIN - age_minutes
    return age_minutes - PREFERRED_AGE_MINUTES_MAX


def _validate_embedding_vector(
    value: Sequence[float],
    *,
    dimensions: int,
    label: str,
) -> list[float]:
    vector = [float(component) for component in value]
    if len(vector) != dimensions:
        raise EngagementEmbeddingError(
            f"{label} length {len(vector)} does not match expected dimensions {dimensions}"
        )
    return vector


def _chunked(values: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _sortable_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return _ensure_aware_utc(value)


def _ensure_aware_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
