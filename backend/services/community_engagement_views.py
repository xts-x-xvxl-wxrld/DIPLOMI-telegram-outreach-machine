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

class EngagementServiceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class EngagementNotFound(EngagementServiceError):
    pass


class EngagementConflict(EngagementServiceError):
    pass


class EngagementValidationError(EngagementServiceError):
    pass


@dataclass(frozen=True)
class EngagementSettingsView:
    community_id: UUID
    mode: str
    allow_join: bool
    allow_post: bool
    reply_only: bool
    require_approval: bool
    max_posts_per_day: int
    min_minutes_between_posts: int
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    assigned_account_id: UUID | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class EngagementCandidateCreationResult:
    candidate: EngagementCandidate
    created: bool
    reason: str


@dataclass(frozen=True)
class EngagementTargetView:
    id: UUID
    community_id: UUID | None
    community_title: str | None
    submitted_ref: str
    submitted_ref_type: str
    status: str
    allow_join: bool
    allow_detect: bool
    allow_post: bool
    notes: str | None
    added_by: str
    approved_by: str | None
    approved_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EngagementTargetListResult:
    items: list[EngagementTargetView]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True)
class EngagementTargetResolveSummary:
    target_id: UUID
    status: str
    community_id: UUID | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "job_type": "engagement_target.resolve",
            "target_id": str(self.target_id),
            "community_id": str(self.community_id) if self.community_id else None,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class EngagementCandidateView:
    id: UUID
    community_id: UUID
    community_title: str | None
    topic_id: UUID
    topic_name: str
    source_tg_message_id: int | None
    source_excerpt: str | None
    detected_reason: str
    suggested_reply: str | None
    final_reply: str | None
    prompt_profile_id: UUID | None
    prompt_profile_version_id: UUID | None
    prompt_render_summary: dict[str, Any] | None
    risk_notes: list[str]
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class EngagementCandidateRevisionView:
    id: UUID
    candidate_id: UUID
    revision_number: int
    reply_text: str
    edited_by: str
    edit_reason: str | None
    created_at: datetime


@dataclass(frozen=True)
class EngagementCandidateListResult:
    items: list[EngagementCandidateView]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True)
class EngagementActionView:
    id: UUID
    candidate_id: UUID | None
    community_id: UUID
    telegram_account_id: UUID
    action_type: str
    status: str
    outbound_text: str | None
    reply_to_tg_message_id: int | None
    sent_tg_message_id: int | None
    scheduled_at: datetime | None
    sent_at: datetime | None
    error_message: str | None
    created_at: datetime


@dataclass(frozen=True)
class EngagementActionListResult:
    items: list[EngagementActionView]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True)
class EngagementSemanticRolloutBand:
    label: str
    min_similarity: float
    max_similarity: float
    total: int
    pending: int
    approved: int
    rejected: int
    expired: int
    approval_rate: float | None
    average_similarity: float | None


@dataclass(frozen=True)
class EngagementSemanticRolloutSummary:
    window_days: int
    community_id: UUID | None
    topic_id: UUID | None
    total_semantic_candidates: int
    reviewed_semantic_candidates: int
    pending: int
    approved: int
    rejected: int
    expired: int
    approval_rate: float | None
    bands: list[EngagementSemanticRolloutBand]


@dataclass(frozen=True)
class EngagementPromptProfileView:
    id: UUID
    name: str
    description: str | None
    active: bool
    model: str
    temperature: Decimal
    max_output_tokens: int
    system_prompt: str
    user_prompt_template: str
    output_schema_name: str
    current_version_number: int | None
    current_version_id: UUID | None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EngagementPromptProfileListResult:
    items: list[EngagementPromptProfileView]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True)
class EngagementPromptProfileVersionView:
    id: UUID
    prompt_profile_id: UUID
    version_number: int
    model: str
    temperature: Decimal
    max_output_tokens: int
    system_prompt: str
    user_prompt_template: str
    output_schema_name: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class EngagementPromptPreview:
    profile_id: UUID | None
    profile_name: str
    version_id: UUID | None
    version_number: int | None
    model: str
    temperature: Decimal
    max_output_tokens: int
    system_prompt: str
    user_prompt_template: str
    rendered_user_prompt: str
    variables: dict[str, Any]


@dataclass(frozen=True)
class EngagementStyleRuleView:
    id: UUID
    scope_type: str
    scope_id: UUID | None
    name: str
    rule_text: str
    active: bool
    priority: int
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EngagementStyleRuleListResult:
    items: list[EngagementStyleRuleView]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True)
class PromptProfileSelection:
    profile: EngagementPromptProfile | None
    version: EngagementPromptProfileVersion | None
    fallback: EngagementPromptPreview | None = None


@dataclass(frozen=True)
class StyleRuleBundle:
    global_rules: list[str]
    account_rules: list[str]
    community_rules: list[str]
    topic_rules: list[str]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "global": self.global_rules,
            "account": self.account_rules,
            "community": self.community_rules,
            "topic": self.topic_rules,
        }

__all__ = [
    "EngagementServiceError",
    "EngagementNotFound",
    "EngagementConflict",
    "EngagementValidationError",
    "EngagementSettingsView",
    "EngagementCandidateCreationResult",
    "EngagementTargetView",
    "EngagementTargetListResult",
    "EngagementTargetResolveSummary",
    "EngagementCandidateView",
    "EngagementCandidateRevisionView",
    "EngagementCandidateListResult",
    "EngagementActionView",
    "EngagementActionListResult",
    "EngagementSemanticRolloutBand",
    "EngagementSemanticRolloutSummary",
    "EngagementPromptProfileView",
    "EngagementPromptProfileListResult",
    "EngagementPromptProfileVersionView",
    "EngagementPromptPreview",
    "EngagementStyleRuleView",
    "EngagementStyleRuleListResult",
    "PromptProfileSelection",
    "StyleRuleBundle",
]
