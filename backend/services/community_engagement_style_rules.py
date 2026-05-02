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

async def list_style_rules(
    db: AsyncSession,
    *,
    scope_type: str | None = None,
    scope_id: UUID | None = None,
    active: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> EngagementStyleRuleListResult:
    safe_limit = max(min(limit, 100), 1)
    safe_offset = max(offset, 0)
    filters = []
    if scope_type is not None:
        _validate_style_scope(scope_type, scope_id, allow_missing_scope_id=True)
        filters.append(EngagementStyleRule.scope_type == scope_type)
    if scope_id is not None:
        filters.append(EngagementStyleRule.scope_id == scope_id)
    if active is not None:
        filters.append(EngagementStyleRule.active.is_(active))
    total_query = select(func.count(EngagementStyleRule.id))
    query = (
        select(EngagementStyleRule)
        .order_by(EngagementStyleRule.scope_type, EngagementStyleRule.priority, EngagementStyleRule.created_at)
        .limit(safe_limit)
        .offset(safe_offset)
    )
    if filters:
        total_query = total_query.where(*filters)
        query = query.where(*filters)
    total = int(await db.scalar(total_query) or 0)
    rows = await db.scalars(query)
    return EngagementStyleRuleListResult(
        items=[_style_rule_view(rule) for rule in rows],
        limit=safe_limit,
        offset=safe_offset,
        total=total,
    )


async def get_style_rule(db: AsyncSession, rule_id: UUID) -> EngagementStyleRuleView:
    rule = await db.get(EngagementStyleRule, rule_id)
    if rule is None:
        raise EngagementNotFound("style_rule_not_found", "Engagement style rule not found")
    return _style_rule_view(rule)


async def create_style_rule(
    db: AsyncSession,
    *,
    payload: Any,
    created_by: str,
) -> EngagementStyleRuleView:
    scope_type = str(payload.scope_type)
    _validate_style_scope(scope_type, payload.scope_id)
    rule_text = _required_text(payload.rule_text, field="rule_text")
    now = _utcnow()
    rule = EngagementStyleRule(
        id=uuid.uuid4(),
        scope_type=scope_type,
        scope_id=payload.scope_id,
        name=_required_text(payload.name, field="name"),
        rule_text=rule_text,
        active=bool(payload.active),
        priority=int(payload.priority),
        created_by=_required_text(created_by, field="created_by"),
        updated_by=_required_text(created_by, field="updated_by"),
        created_at=now,
        updated_at=now,
    )
    db.add(rule)
    await db.flush()
    return _style_rule_view(rule)


async def update_style_rule(
    db: AsyncSession,
    *,
    rule_id: UUID,
    payload: Any,
    updated_by: str,
) -> EngagementStyleRuleView:
    rule = await db.get(EngagementStyleRule, rule_id)
    if rule is None:
        raise EngagementNotFound("style_rule_not_found", "Engagement style rule not found")
    scope_type = rule.scope_type
    scope_id = rule.scope_id
    if _field_was_set(payload, "scope_type") and payload.scope_type is not None:
        scope_type = str(payload.scope_type)
    if _field_was_set(payload, "scope_id"):
        scope_id = payload.scope_id
    _validate_style_scope(scope_type, scope_id)
    if _field_was_set(payload, "name") and payload.name is not None:
        rule.name = _required_text(payload.name, field="name")
    if _field_was_set(payload, "rule_text") and payload.rule_text is not None:
        rule_text = _required_text(payload.rule_text, field="rule_text")
        rule.rule_text = rule_text
    if _field_was_set(payload, "active") and payload.active is not None:
        rule.active = bool(payload.active)
    if _field_was_set(payload, "priority") and payload.priority is not None:
        rule.priority = int(payload.priority)
    rule.scope_type = scope_type
    rule.scope_id = scope_id
    rule.updated_by = _required_text(updated_by, field="updated_by")
    rule.updated_at = _utcnow()
    await db.flush()
    return _style_rule_view(rule)


async def list_active_style_rules_for_prompt(
    db: AsyncSession,
    *,
    account_id: UUID | None,
    community_id: UUID,
    topic_id: UUID,
) -> StyleRuleBundle:
    scope_filters = [
        (EngagementStyleRule.scope_type == EngagementStyleRuleScope.GLOBAL.value)
        & EngagementStyleRule.scope_id.is_(None),
        (EngagementStyleRule.scope_type == EngagementStyleRuleScope.COMMUNITY.value)
        & (EngagementStyleRule.scope_id == community_id),
        (EngagementStyleRule.scope_type == EngagementStyleRuleScope.TOPIC.value)
        & (EngagementStyleRule.scope_id == topic_id),
    ]
    if account_id is not None:
        scope_filters.append(
            (EngagementStyleRule.scope_type == EngagementStyleRuleScope.ACCOUNT.value)
            & (EngagementStyleRule.scope_id == account_id)
        )
    rows = await db.scalars(
        select(EngagementStyleRule)
        .where(EngagementStyleRule.active.is_(True), *scope_filters[:1])
        .order_by(EngagementStyleRule.priority, EngagementStyleRule.created_at)
    )
    global_rules = [rule.rule_text for rule in rows]

    async def _scope_rules(scope_type: str, scope_id_value: UUID | None) -> list[str]:
        if scope_id_value is None:
            return []
        scoped = await db.scalars(
            select(EngagementStyleRule)
            .where(
                EngagementStyleRule.active.is_(True),
                EngagementStyleRule.scope_type == scope_type,
                EngagementStyleRule.scope_id == scope_id_value,
            )
            .order_by(EngagementStyleRule.priority, EngagementStyleRule.created_at)
        )
        return [rule.rule_text for rule in scoped]

    return StyleRuleBundle(
        global_rules=global_rules,
        account_rules=await _scope_rules(EngagementStyleRuleScope.ACCOUNT.value, account_id),
        community_rules=await _scope_rules(EngagementStyleRuleScope.COMMUNITY.value, community_id),
        topic_rules=await _scope_rules(EngagementStyleRuleScope.TOPIC.value, topic_id),
    )


def _style_rule_view(rule: EngagementStyleRule) -> EngagementStyleRuleView:
    return EngagementStyleRuleView(
        id=rule.id,
        scope_type=rule.scope_type,
        scope_id=rule.scope_id,
        name=rule.name,
        rule_text=rule.rule_text,
        active=rule.active,
        priority=rule.priority,
        created_by=rule.created_by,
        updated_by=rule.updated_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _validate_style_scope(
    scope_type: str,
    scope_id: UUID | None,
    *,
    allow_missing_scope_id: bool = False,
) -> None:
    allowed = {item.value for item in EngagementStyleRuleScope}
    if scope_type not in allowed:
        raise EngagementValidationError("invalid_style_scope", "Unknown engagement style rule scope")
    if scope_type == EngagementStyleRuleScope.GLOBAL.value:
        if scope_id is not None:
            raise EngagementValidationError("invalid_style_scope_id", "Global style rules cannot have scope_id")
        return
    if scope_id is None and not allow_missing_scope_id:
        raise EngagementValidationError("style_scope_id_required", "Non-global style rules require scope_id")


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
    "list_style_rules",
    "get_style_rule",
    "create_style_rule",
    "update_style_rule",
    "list_active_style_rules_for_prompt",
]
