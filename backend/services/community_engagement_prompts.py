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

async def create_prompt_profile(
    db: AsyncSession,
    *,
    payload: Any,
    created_by: str,
) -> EngagementPromptProfileView:
    values = _prompt_profile_values(payload)
    now = _utcnow()
    profile = EngagementPromptProfile(
        id=uuid.uuid4(),
        name=values["name"],
        description=values["description"],
        active=False,
        model=values["model"],
        temperature=values["temperature"],
        max_output_tokens=values["max_output_tokens"],
        system_prompt=values["system_prompt"],
        user_prompt_template=values["user_prompt_template"],
        output_schema_name=values["output_schema_name"],
        created_by=_required_text(created_by, field="created_by"),
        updated_by=_required_text(created_by, field="updated_by"),
        created_at=now,
        updated_at=now,
    )
    db.add(profile)
    version = _new_prompt_version(profile, version_number=1, created_by=created_by, now=now)
    db.add(version)
    if bool(getattr(payload, "active", False)):
        await _deactivate_other_prompt_profiles(db, profile.id)
        profile.active = True
    await db.flush()
    return await _prompt_profile_view(db, profile)


async def list_prompt_profiles(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
) -> EngagementPromptProfileListResult:
    safe_limit = max(min(limit, 100), 1)
    safe_offset = max(offset, 0)
    total = int(await db.scalar(select(func.count(EngagementPromptProfile.id))) or 0)
    rows = await db.scalars(
        select(EngagementPromptProfile)
        .order_by(EngagementPromptProfile.active.desc(), EngagementPromptProfile.updated_at.desc())
        .limit(safe_limit)
        .offset(safe_offset)
    )
    return EngagementPromptProfileListResult(
        items=[await _prompt_profile_view(db, profile) for profile in rows],
        limit=safe_limit,
        offset=safe_offset,
        total=total,
    )


async def get_prompt_profile(db: AsyncSession, profile_id: UUID) -> EngagementPromptProfileView:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    return await _prompt_profile_view(db, profile)


async def update_prompt_profile(
    db: AsyncSession,
    *,
    profile_id: UUID,
    payload: Any,
    updated_by: str,
) -> EngagementPromptProfileView:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    values = _prompt_profile_values(payload, current=profile)
    _validate_prompt_template(values["user_prompt_template"])

    profile.name = values["name"]
    profile.description = values["description"]
    profile.model = values["model"]
    profile.temperature = values["temperature"]
    profile.max_output_tokens = values["max_output_tokens"]
    profile.system_prompt = values["system_prompt"]
    profile.user_prompt_template = values["user_prompt_template"]
    profile.output_schema_name = values["output_schema_name"]
    profile.updated_by = _required_text(updated_by, field="updated_by")
    profile.updated_at = _utcnow()
    version = _new_prompt_version(
        profile,
        version_number=await _next_prompt_version_number(db, profile.id),
        created_by=updated_by,
        now=profile.updated_at,
    )
    db.add(version)
    if _field_was_set(payload, "active") and bool(payload.active):
        await _deactivate_other_prompt_profiles(db, profile.id)
        profile.active = True
    elif _field_was_set(payload, "active"):
        profile.active = bool(payload.active)
    await db.flush()
    return await _prompt_profile_view(db, profile)


async def activate_prompt_profile(
    db: AsyncSession,
    *,
    profile_id: UUID,
    updated_by: str,
) -> EngagementPromptProfileView:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    await _deactivate_other_prompt_profiles(db, profile_id)
    profile.active = True
    profile.updated_by = _required_text(updated_by, field="updated_by")
    profile.updated_at = _utcnow()
    await db.flush()
    return await _prompt_profile_view(db, profile)


async def duplicate_prompt_profile(
    db: AsyncSession,
    *,
    profile_id: UUID,
    created_by: str,
    name: str | None = None,
) -> EngagementPromptProfileView:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    now = _utcnow()
    copy = EngagementPromptProfile(
        id=uuid.uuid4(),
        name=_required_text(name, field="name") if name else f"{profile.name} copy",
        description=profile.description,
        active=False,
        model=profile.model,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        system_prompt=profile.system_prompt,
        user_prompt_template=profile.user_prompt_template,
        output_schema_name=profile.output_schema_name,
        created_by=_required_text(created_by, field="created_by"),
        updated_by=_required_text(created_by, field="updated_by"),
        created_at=now,
        updated_at=now,
    )
    db.add(copy)
    db.add(_new_prompt_version(copy, version_number=1, created_by=created_by, now=now))
    await db.flush()
    return await _prompt_profile_view(db, copy)


async def rollback_prompt_profile(
    db: AsyncSession,
    *,
    profile_id: UUID,
    version_id: UUID,
    updated_by: str,
) -> EngagementPromptProfileView:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    version = await db.scalar(
        select(EngagementPromptProfileVersion).where(
            EngagementPromptProfileVersion.id == version_id,
            EngagementPromptProfileVersion.prompt_profile_id == profile_id,
        )
    )
    if version is None:
        raise EngagementNotFound("prompt_profile_version_not_found", "Prompt profile version not found")
    profile.model = version.model
    profile.temperature = version.temperature
    profile.max_output_tokens = version.max_output_tokens
    profile.system_prompt = version.system_prompt
    profile.user_prompt_template = version.user_prompt_template
    profile.output_schema_name = version.output_schema_name
    profile.updated_by = _required_text(updated_by, field="updated_by")
    profile.updated_at = _utcnow()
    db.add(
        _new_prompt_version(
            profile,
            version_number=await _next_prompt_version_number(db, profile.id),
            created_by=updated_by,
            now=profile.updated_at,
        )
    )
    await db.flush()
    return await _prompt_profile_view(db, profile)


async def list_prompt_profile_versions(
    db: AsyncSession,
    *,
    profile_id: UUID,
) -> list[EngagementPromptProfileVersionView]:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    rows = await db.scalars(
        select(EngagementPromptProfileVersion)
        .where(EngagementPromptProfileVersion.prompt_profile_id == profile_id)
        .order_by(EngagementPromptProfileVersion.version_number.desc())
    )
    return [_prompt_version_view(row) for row in rows]


async def select_active_prompt_profile(db: AsyncSession) -> PromptProfileSelection:
    profile = await db.scalar(
        select(EngagementPromptProfile)
        .where(EngagementPromptProfile.active.is_(True))
        .order_by(EngagementPromptProfile.updated_at.desc(), EngagementPromptProfile.id.desc())
        .limit(1)
    )
    if profile is None:
        return PromptProfileSelection(
            profile=None,
            version=None,
            fallback=_default_prompt_preview(),
        )
    version = await _latest_prompt_version(db, profile.id)
    return PromptProfileSelection(profile=profile, version=version)


async def preview_prompt_profile(
    db: AsyncSession,
    *,
    profile_id: UUID | None,
    variables: dict[str, Any] | None = None,
) -> EngagementPromptPreview:
    if profile_id is None:
        default = _default_prompt_preview()
        return _render_prompt_preview(default, variables or _synthetic_prompt_variables())
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    latest = await _latest_prompt_version(db, profile.id)
    preview = EngagementPromptPreview(
        profile_id=profile.id,
        profile_name=profile.name,
        version_id=latest.id if latest is not None else None,
        version_number=latest.version_number if latest is not None else None,
        model=profile.model,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        system_prompt=profile.system_prompt,
        user_prompt_template=profile.user_prompt_template,
        rendered_user_prompt="",
        variables={},
    )
    return _render_prompt_preview(preview, variables or _synthetic_prompt_variables())


def render_prompt_template(template: str, variables: dict[str, Any]) -> str:
    _validate_prompt_template(template)
    return _render_template(template, variables)


async def _deactivate_other_prompt_profiles(db: AsyncSession, active_profile_id: UUID) -> None:
    rows = await db.scalars(
        select(EngagementPromptProfile).where(
            EngagementPromptProfile.id != active_profile_id,
            EngagementPromptProfile.active.is_(True),
        )
    )
    now = _utcnow()
    for profile in rows:
        profile.active = False
        profile.updated_at = now


def _new_prompt_version(
    profile: EngagementPromptProfile,
    *,
    version_number: int,
    created_by: str,
    now: datetime,
) -> EngagementPromptProfileVersion:
    return EngagementPromptProfileVersion(
        id=uuid.uuid4(),
        prompt_profile_id=profile.id,
        version_number=version_number,
        model=profile.model,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        system_prompt=profile.system_prompt,
        user_prompt_template=profile.user_prompt_template,
        output_schema_name=profile.output_schema_name,
        created_by=_required_text(created_by, field="created_by"),
        created_at=now,
    )


def _prompt_profile_values(payload: Any, current: EngagementPromptProfile | None = None) -> dict[str, Any]:
    name = current.name if current is not None else None
    description = current.description if current is not None else None
    model = current.model if current is not None else None
    temperature = current.temperature if current is not None else Decimal("0.2")
    max_output_tokens = current.max_output_tokens if current is not None else 1000
    system_prompt = current.system_prompt if current is not None else None
    user_prompt_template = current.user_prompt_template if current is not None else None
    output_schema_name = current.output_schema_name if current is not None else "engagement_detection_v1"

    if current is None or _field_was_set(payload, "name"):
        name = _required_text(payload.name, field="name")
    if current is None or _field_was_set(payload, "description"):
        description = _optional_text(payload.description)
    if (current is None or _field_was_set(payload, "model")) and payload.model is not None:
        model = _required_text(payload.model, field="model")
    if (current is None or _field_was_set(payload, "temperature")) and payload.temperature is not None:
        temperature = Decimal(str(payload.temperature))
    if (
        current is None or _field_was_set(payload, "max_output_tokens")
    ) and payload.max_output_tokens is not None:
        max_output_tokens = int(payload.max_output_tokens)
    if (current is None or _field_was_set(payload, "system_prompt")) and payload.system_prompt is not None:
        system_prompt = _required_text(payload.system_prompt, field="system_prompt")
    if (
        current is None or _field_was_set(payload, "user_prompt_template")
    ) and payload.user_prompt_template is not None:
        user_prompt_template = _required_multiline_text(
            payload.user_prompt_template,
            field="user_prompt_template",
        )
    if (
        current is None or _field_was_set(payload, "output_schema_name")
    ) and payload.output_schema_name is not None:
        output_schema_name = _required_text(payload.output_schema_name, field="output_schema_name")

    assert name is not None
    assert model is not None
    assert system_prompt is not None
    assert user_prompt_template is not None
    assert output_schema_name is not None
    if temperature < Decimal("0") or temperature > Decimal("2"):
        raise EngagementValidationError("invalid_temperature", "Prompt profile temperature must be 0-2")
    if max_output_tokens < 128 or max_output_tokens > 4000:
        raise EngagementValidationError(
            "invalid_max_output_tokens",
            "Prompt profile max output tokens must be between 128 and 4000",
        )
    _validate_safe_admin_text(system_prompt, code_prefix="prompt")
    _validate_prompt_template(user_prompt_template)
    return {
        "name": name,
        "description": description,
        "model": model,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "system_prompt": system_prompt,
        "user_prompt_template": user_prompt_template,
        "output_schema_name": output_schema_name,
    }


async def _prompt_profile_view(
    db: AsyncSession,
    profile: EngagementPromptProfile,
) -> EngagementPromptProfileView:
    latest = await _latest_prompt_version(db, profile.id)
    return EngagementPromptProfileView(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        active=profile.active,
        model=profile.model,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        system_prompt=profile.system_prompt,
        user_prompt_template=profile.user_prompt_template,
        output_schema_name=profile.output_schema_name,
        current_version_number=latest.version_number if latest is not None else None,
        current_version_id=latest.id if latest is not None else None,
        created_by=profile.created_by,
        updated_by=profile.updated_by,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


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


async def _next_prompt_version_number(db: AsyncSession, profile_id: UUID) -> int:
    value = await db.scalar(
        select(func.max(EngagementPromptProfileVersion.version_number)).where(
            EngagementPromptProfileVersion.prompt_profile_id == profile_id
        )
    )
    try:
        return int(value or 0) + 1
    except (TypeError, ValueError):
        return 1


def _validate_prompt_template(template: str) -> None:
    for match in _TEMPLATE_RE.finditer(template):
        key = match.group(1).strip()
        if key not in _ALLOWED_PROMPT_VARIABLES:
            raise EngagementValidationError(
                "invalid_prompt_variable",
                f"Prompt template variable is not allowed: {key}",
            )


def _prompt_version_view(version: EngagementPromptProfileVersion) -> EngagementPromptProfileVersionView:
    return EngagementPromptProfileVersionView(
        id=version.id,
        prompt_profile_id=version.prompt_profile_id,
        version_number=version.version_number,
        model=version.model,
        temperature=version.temperature,
        max_output_tokens=version.max_output_tokens,
        system_prompt=version.system_prompt,
        user_prompt_template=version.user_prompt_template,
        output_schema_name=version.output_schema_name,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _default_prompt_preview() -> EngagementPromptPreview:
    return EngagementPromptPreview(
        profile_id=None,
        profile_name="Default engagement prompt",
        version_id=None,
        version_number=None,
        model="default",
        temperature=Decimal("0.2"),
        max_output_tokens=1000,
        system_prompt=(
            "You draft transparent, helpful public replies for an approved operator account. "
            "Prefer no reply over a weak reply."
        ),
        user_prompt_template=(
            "Community: {{community.title}} (@{{community.username}})\n"
            "Topic: {{topic.name}}\n"
            "Guidance: {{topic.stance_guidance}}\n"
            "Good examples: {{topic.example_good_replies}}\n"
            "Bad examples to avoid: {{topic.example_bad_replies}}\n"
            "Global style: {{style.global}}\n"
            "Account style: {{style.account}}\n"
            "Community style: {{style.community}}\n"
            "Source post: {{source_post.text}}\n"
            "Source message id: {{source_post.tg_message_id}}\n"
            "Source date: {{source_post.message_date}}\n"
            "Reply context: {{reply_context}}\n"
            "Community context: {{community_context.latest_summary}}\n"
            "Themes: {{community_context.dominant_themes}}"
        ),
        rendered_user_prompt="",
        variables={},
    )


async def _latest_prompt_version(
    db: AsyncSession,
    profile_id: UUID,
) -> EngagementPromptProfileVersion | None:
    return await db.scalar(
        select(EngagementPromptProfileVersion)
        .where(EngagementPromptProfileVersion.prompt_profile_id == profile_id)
        .order_by(EngagementPromptProfileVersion.version_number.desc())
        .limit(1)
    )


def _render_prompt_preview(
    preview: EngagementPromptPreview,
    variables: dict[str, Any],
) -> EngagementPromptPreview:
    _validate_prompt_template(preview.user_prompt_template)
    rendered = _render_template(preview.user_prompt_template, variables)
    return EngagementPromptPreview(
        profile_id=preview.profile_id,
        profile_name=preview.profile_name,
        version_id=preview.version_id,
        version_number=preview.version_number,
        model=preview.model,
        temperature=preview.temperature,
        max_output_tokens=preview.max_output_tokens,
        system_prompt=preview.system_prompt,
        user_prompt_template=preview.user_prompt_template,
        rendered_user_prompt=rendered,
        variables=variables,
    )


def _synthetic_prompt_variables() -> dict[str, Any]:
    source_post = {
        "tg_message_id": 123,
        "text": "Has anyone compared open-source CRM options?",
        "message_date": "2026-04-20T10:00:00+00:00",
    }
    return {
        "community": {
            "title": "Example Operators",
            "username": "example_operators",
            "description": "A public group discussing SaaS operations.",
        },
        "topic": {
            "name": "Open-source CRM",
            "description": "CRM tooling discussions",
            "stance_guidance": "Be factual, brief, and non-salesy.",
            "trigger_keywords": ["crm", "open source"],
            "negative_keywords": [],
            "example_good_replies": ["Compare data ownership, integrations, and exit paths first."],
            "example_bad_replies": ["Buy our tool now."],
        },
        "style": {
            "global": ["Keep replies public and useful."],
            "account": [],
            "community": ["Keep replies under 3 sentences."],
            "topic": ["Discuss practical evaluation criteria."],
        },
        "source_post": source_post,
        "reply_context": "A previous message asks about migration effort and data export.",
        "messages": [source_post],
        "community_context": {
            "latest_summary": "Members compare sales and support tooling.",
            "dominant_themes": ["crm", "automation"],
        },
    }


def _render_template(template: str, variables: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = _lookup_template_variable(variables, key)
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        if isinstance(value, dict):
            return str(value)
        return "" if value is None else str(value)

    return _TEMPLATE_RE.sub(replace, template)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _required_multiline_text(value: str | None, *, field: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise EngagementValidationError(f"{field}_required", f"{field} is required")
    return cleaned


def _validate_safe_admin_text(value: str, *, code_prefix: str) -> None:
    lowered = value.casefold()
    disallowed_markers = (
        "ask for dm",
        "ask users to dm",
        "move to dm",
        "send them a direct message",
        "pretend to be",
        "act like a normal member",
        "create fake consensus",
        "make fake consensus",
        "hidden sponsorship",
        "evade moderation",
        "harass",
        "target individual",
        "target individuals",
    )
    for marker in disallowed_markers:
        if marker in lowered and f"do not {marker}" not in lowered and f"don't {marker}" not in lowered:
            raise EngagementValidationError(
                f"unsafe_{code_prefix}",
                "Admin-controlled engagement text cannot permit DMs, impersonation, "
                "hidden sponsorship, harassment, fake consensus, or moderation evasion",
            )


def _lookup_template_variable(variables: dict[str, Any], key: str) -> Any:
    current: Any = variables
    for part in key.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current

__all__ = [
    "create_prompt_profile",
    "list_prompt_profiles",
    "get_prompt_profile",
    "update_prompt_profile",
    "activate_prompt_profile",
    "duplicate_prompt_profile",
    "rollback_prompt_profile",
    "list_prompt_profile_versions",
    "select_active_prompt_profile",
    "preview_prompt_profile",
    "render_prompt_template",
]
