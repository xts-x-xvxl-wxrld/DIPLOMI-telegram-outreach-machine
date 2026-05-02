# ruff: noqa: F401,F403,F405
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone
from decimal import Decimal
import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.enums import (
    AccountPool,
    AccountStatus,
    CommunityAccountMembershipStatus,
    CommunitySource,
    CommunityStatus,
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementStyleRuleScope,
    EngagementTargetRefType,
    EngagementTargetStatus,
    TelegramEntityIntakeStatus,
    TelegramEntityType,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementAction,
    EngagementCandidate,
    EngagementCandidateRevision,
    EngagementPromptProfile,
    EngagementPromptProfileVersion,
    EngagementStyleRule,
    EngagementTarget,
    EngagementTopic,
    TelegramAccount,
)
from backend.services.seed_import import normalize_telegram_seed
from backend.services.seed_resolution import TransientResolveError
from backend.services.telegram_entity_intake import (
    TelegramEntityInfo,
    TelegramEntityResolveOutcome,
    TelegramEntityResolverAdapter,
)
from backend.services.community_engagement_views import *

_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
_SEMANTIC_ROLLOUT_BANDS = (
    ("0.90-1.00", 0.90, 1.0),
    ("0.80-0.89", 0.80, 0.90),
    ("0.70-0.79", 0.70, 0.80),
    ("0.62-0.69", 0.62, 0.70),
    ("0.00-0.61", 0.00, 0.62),
)
_ALLOWED_PROMPT_VARIABLES = {
    "community.title",
    "community.username",
    "community.description",
    "topic.name",
    "topic.description",
    "topic.stance_guidance",
    "topic.trigger_keywords",
    "topic.negative_keywords",
    "topic.example_good_replies",
    "topic.example_bad_replies",
    "style.global",
    "style.account",
    "style.community",
    "style.topic",
    "source_post.text",
    "source_post.tg_message_id",
    "source_post.message_date",
    "reply_context",
    "messages",
    "community_context.latest_summary",
    "community_context.dominant_themes",
}

async def create_topic(db: AsyncSession, *, payload: Any) -> EngagementTopic:
    name = _required_text(payload.name, field="name")
    description = _optional_text(payload.description)
    stance_guidance = _required_text(payload.stance_guidance, field="stance_guidance")
    trigger_keywords = normalize_keywords(payload.trigger_keywords)
    negative_keywords = normalize_keywords(payload.negative_keywords)
    example_good_replies = normalize_text_list(
        payload.example_good_replies,
        deduplicate_casefold=True,
    )
    example_bad_replies = normalize_text_list(payload.example_bad_replies)

    validate_topic_policy(
        name=name,
        description=description,
        stance_guidance=stance_guidance,
        trigger_keywords=trigger_keywords,
        example_good_replies=example_good_replies,
        example_bad_replies=example_bad_replies,
        active=payload.active,
    )
    await _ensure_unique_topic_name(db, name)

    now = _utcnow()
    topic = EngagementTopic(
        id=uuid.uuid4(),
        name=name,
        description=description,
        stance_guidance=stance_guidance,
        trigger_keywords=trigger_keywords,
        negative_keywords=negative_keywords,
        example_good_replies=example_good_replies,
        example_bad_replies=example_bad_replies,
        active=payload.active,
        created_at=now,
        updated_at=now,
    )
    db.add(topic)
    await db.flush()
    return topic


async def update_topic(db: AsyncSession, *, topic_id: UUID, payload: Any) -> EngagementTopic:
    topic = await db.get(EngagementTopic, topic_id)
    if topic is None:
        raise EngagementNotFound("not_found", "Engagement topic not found")

    next_name = topic.name
    next_description = topic.description
    next_guidance = topic.stance_guidance
    next_trigger_keywords = list(topic.trigger_keywords or [])
    next_negative_keywords = list(topic.negative_keywords or [])
    next_good_replies = list(topic.example_good_replies or [])
    next_bad_replies = list(topic.example_bad_replies or [])
    next_active = topic.active

    if _field_was_set(payload, "name"):
        next_name = _required_text(payload.name, field="name")
    if _field_was_set(payload, "description"):
        next_description = _optional_text(payload.description)
    if _field_was_set(payload, "stance_guidance"):
        next_guidance = _required_text(payload.stance_guidance, field="stance_guidance")
    if _field_was_set(payload, "trigger_keywords"):
        next_trigger_keywords = normalize_keywords(payload.trigger_keywords)
    if _field_was_set(payload, "negative_keywords"):
        next_negative_keywords = normalize_keywords(payload.negative_keywords)
    if _field_was_set(payload, "example_good_replies"):
        next_good_replies = normalize_text_list(
            payload.example_good_replies,
            deduplicate_casefold=True,
        )
    if _field_was_set(payload, "example_bad_replies"):
        next_bad_replies = normalize_text_list(payload.example_bad_replies)
    if _field_was_set(payload, "active"):
        next_active = payload.active

    validate_topic_policy(
        name=next_name,
        description=next_description,
        stance_guidance=next_guidance,
        trigger_keywords=next_trigger_keywords,
        example_good_replies=next_good_replies,
        example_bad_replies=next_bad_replies,
        active=next_active,
    )
    if next_name.casefold() != topic.name.casefold():
        await _ensure_unique_topic_name(db, next_name, excluding_topic_id=topic_id)

    topic.name = next_name
    topic.description = next_description
    topic.stance_guidance = next_guidance
    topic.trigger_keywords = next_trigger_keywords
    topic.negative_keywords = next_negative_keywords
    topic.example_good_replies = next_good_replies
    topic.example_bad_replies = next_bad_replies
    topic.active = next_active
    topic.updated_at = _utcnow()
    await db.flush()
    return topic


async def list_active_topics(db: AsyncSession) -> list[EngagementTopic]:
    rows = await db.scalars(
        select(EngagementTopic).where(EngagementTopic.active.is_(True)).order_by(EngagementTopic.name)
    )
    return list(rows)


async def list_topics(db: AsyncSession) -> list[EngagementTopic]:
    rows = await db.scalars(select(EngagementTopic).order_by(EngagementTopic.name))
    return list(rows)


async def get_topic(db: AsyncSession, topic_id: UUID) -> EngagementTopic:
    topic = await db.get(EngagementTopic, topic_id)
    if topic is None:
        raise EngagementNotFound("not_found", "Engagement topic not found")
    return topic


async def add_topic_example(
    db: AsyncSession,
    *,
    topic_id: UUID,
    example_type: str,
    example: str,
) -> EngagementTopic:
    topic = await db.get(EngagementTopic, topic_id)
    if topic is None:
        raise EngagementNotFound("not_found", "Engagement topic not found")
    cleaned = _required_text(example, field="example")
    if example_type == "good":
        existing_examples = list(topic.example_good_replies or [])
        if cleaned.casefold() not in {item.casefold() for item in existing_examples}:
            topic.example_good_replies = [*existing_examples, cleaned]
        else:
            topic.example_good_replies = existing_examples
    elif example_type == "bad":
        topic.example_bad_replies = [*(topic.example_bad_replies or []), cleaned]
    else:
        raise EngagementValidationError("invalid_example_type", "Example type must be good or bad")
    topic.updated_at = _utcnow()
    await db.flush()
    return topic


async def remove_topic_example(
    db: AsyncSession,
    *,
    topic_id: UUID,
    example_type: str,
    index: int,
) -> EngagementTopic:
    topic = await db.get(EngagementTopic, topic_id)
    if topic is None:
        raise EngagementNotFound("not_found", "Engagement topic not found")
    if example_type == "good":
        values = list(topic.example_good_replies or [])
    elif example_type == "bad":
        values = list(topic.example_bad_replies or [])
    else:
        raise EngagementValidationError("invalid_example_type", "Example type must be good or bad")
    if index < 0 or index >= len(values):
        raise EngagementNotFound("example_not_found", "Topic example not found")
    values.pop(index)
    if example_type == "good":
        topic.example_good_replies = values
    else:
        topic.example_bad_replies = values
    topic.updated_at = _utcnow()
    await db.flush()
    return topic


def normalize_keywords(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        cleaned = " ".join(value.strip().casefold().split())
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            normalized.append(cleaned)
    return normalized


def normalize_text_list(
    values: list[str] | None,
    *,
    deduplicate_casefold: bool = False,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        cleaned = " ".join(value.strip().split())
        if cleaned:
            dedupe_key = cleaned.casefold()
            if deduplicate_casefold and dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(cleaned)
    return normalized


def validate_topic_policy(
    *,
    name: str,
    description: str | None,
    stance_guidance: str,
    trigger_keywords: list[str],
    example_good_replies: list[str],
    example_bad_replies: list[str],
    active: bool,
) -> None:
    _required_text(name, field="name")
    _required_text(stance_guidance, field="stance_guidance")
    has_semantic_profile = bool(description or trigger_keywords or example_good_replies)
    if active and not has_semantic_profile:
        raise EngagementValidationError(
            "topic_requires_semantic_profile",
            "Active engagement topics require description, trigger keywords, or good examples",
        )


async def _ensure_unique_topic_name(
    db: AsyncSession,
    name: str,
    *,
    excluding_topic_id: UUID | None = None,
) -> None:
    query = select(EngagementTopic).where(func.lower(EngagementTopic.name) == name.casefold())
    if excluding_topic_id is not None:
        query = query.where(EngagementTopic.id != excluding_topic_id)
    existing = await db.scalar(query.limit(1))
    if existing is not None:
        raise EngagementConflict(
            "topic_name_exists",
            "An engagement topic with this name already exists",
        )


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _required_text(value: str | None, *, field: str) -> str:
    cleaned = " ".join((value or "").strip().split())
    if not cleaned:
        raise EngagementValidationError(f"{field}_required", f"{field} is required")
    return cleaned


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _field_was_set(payload: Any, field: str) -> bool:
    fields_set = getattr(payload, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(payload, "__fields_set__", set())
    return field in fields_set

__all__ = [
    "create_topic",
    "update_topic",
    "list_active_topics",
    "list_topics",
    "get_topic",
    "add_topic_example",
    "remove_topic_example",
    "normalize_keywords",
    "normalize_text_list",
    "validate_topic_policy",
]
