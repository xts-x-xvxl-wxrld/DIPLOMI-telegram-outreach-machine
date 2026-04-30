# ruff: noqa: F401,F403,F405
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import Settings, get_settings
from backend.db.enums import CollectionRunStatus, EngagementCandidateStatus, EngagementMode
from backend.db.models import (
    AnalysisSummary,
    CollectionRun,
    Community,
    EngagementCandidate,
    EngagementTopic,
    Message,
)
from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import EngagementDetectPayload
from backend.services.community_engagement import (
    EngagementCandidateCreationResult,
    EngagementServiceError,
    EngagementValidationError,
    create_engagement_candidate,
    get_engagement_settings,
    get_joined_membership_for_send,
    has_engagement_target_permission,
    list_active_style_rules_for_prompt,
    list_active_topics,
    render_prompt_template,
    sanitize_candidate_excerpt,
    select_active_prompt_profile,
)
from backend.services.engagement_embeddings import (
    SemanticSelectionStats,
    SemanticTriggerMatch,
    select_semantic_trigger_messages,
)


MAX_MESSAGES_PER_MODEL_CALL = 20
MAX_MESSAGE_CHARS = 500
MAX_MODEL_INPUT_BYTES = 64 * 1024
LOGGER = logging.getLogger(__name__)


DETECTION_INSTRUCTIONS = """You draft transparent, helpful public replies for an approved operator account.
Do not impersonate a normal community member.
Do not create urgency, deception, fake consensus, or claims of personal experience.
Do not target, profile, rank, or evaluate individual people.
Do not suggest direct messages.
Do not mention private/internal analysis.
Only produce a reply when it is genuinely useful and relevant.
Prefer no reply over a weak reply."""

class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


@dataclass(frozen=True)
class DetectionMessage:
    tg_message_id: int | None
    text: str
    message_date: datetime | None
    reply_to_tg_message_id: int | None = None
    reply_context: str | None = None
    is_replyable: bool = False


@dataclass(frozen=True)
class CommunityContext:
    latest_summary: str | None
    dominant_themes: list[str]


@dataclass(frozen=True)
class TriggerCandidate:
    message: DetectionMessage
    semantic_match: SemanticTriggerMatch | None = None


class EngagementDetectionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_engage: bool
    topic_match: str | None = None
    source_tg_message_id: int | None = None
    reason: str = ""
    moment_strength: Literal["weak", "good", "strong"] | None = Field(
        default=None,
        description="Conversation fit strength. Allowed values: weak, good, strong.",
    )
    timeliness: str | None = None
    reply_value: Literal[
        "clarifying_question",
        "practical_tip",
        "correction",
        "resource",
        "other",
        "none",
    ] | None = Field(
        default=None,
        description=(
            "Public reply type, not an assessment of the person. Allowed values: "
            "clarifying_question, practical_tip, correction, resource, other, none."
        ),
    )
    suggested_reply: str | None = None
    risk_notes: list[str] = Field(default_factory=list)


@dataclass
class DetectionSummary:
    community_id: object
    candidates_created: int = 0
    topics_checked: int = 0
    detector_calls: int = 0
    skipped_detector_cap: int = 0
    skipped_no_signal: int = 0
    skipped_dedupe: int = 0
    skipped_stale: int = 0
    skipped_validation: int = 0
    semantic_observability: SemanticSelectionStats = field(default_factory=SemanticSelectionStats)
    semantic_candidates_created: int = 0

    def to_dict(self) -> dict[str, object]:
        semantic = self.semantic_observability.to_dict()
        return {
            "status": "processed",
            "job_type": "engagement.detect",
            "community_id": str(self.community_id),
            "candidates_created": self.candidates_created,
            "topics_checked": self.topics_checked,
            "detector_calls": self.detector_calls,
            "skipped_detector_cap": self.skipped_detector_cap,
            "skipped_no_signal": self.skipped_no_signal,
            "skipped_dedupe": self.skipped_dedupe,
            "skipped_stale": self.skipped_stale,
            "skipped_validation": self.skipped_validation,
            "semantic_topic_embedding_cache_hits": semantic["topic_embedding_cache_hits"],
            "semantic_topic_embedding_cache_misses": semantic["topic_embedding_cache_misses"],
            "semantic_topic_embeddings_created": semantic["topic_embeddings_created"],
            "semantic_message_embedding_cache_hits": semantic["message_embedding_cache_hits"],
            "semantic_message_embedding_cache_misses": semantic["message_embedding_cache_misses"],
            "semantic_message_embeddings_created": semantic["message_embeddings_created"],
            "semantic_messages_considered": semantic["messages_considered"],
            "semantic_messages_rejected_empty_text": semantic["messages_rejected_empty_text"],
            "semantic_messages_rejected_negative": semantic["messages_rejected_negative"],
            "semantic_messages_eligible_for_embedding": semantic["messages_eligible_for_embedding"],
            "semantic_messages_below_threshold": semantic["messages_below_threshold"],
            "semantic_matches_selected": semantic["semantic_matches_selected"],
            "semantic_detector_calls_avoided": semantic["detector_calls_avoided"],
            "semantic_candidates_created": self.semantic_candidates_created,
        }

MAX_MESSAGES_PER_MODEL_CALL = 20
MAX_MESSAGE_CHARS = 500
MAX_MODEL_INPUT_BYTES = 64 * 1024
LOGGER = logging.getLogger("backend.workers.engagement_detect")
DETECTION_INSTRUCTIONS = """You draft transparent, helpful public replies for an approved operator account.
Do not impersonate a normal community member.
Do not create urgency, deception, fake consensus, or claims of personal experience.
Do not target, profile, rank, or evaluate individual people.
Do not suggest direct messages.
Do not mention private/internal analysis.
Only produce a reply when it is genuinely useful and relevant.
Prefer no reply over a weak reply."""
Detector = Callable[[dict[str, Any]], Awaitable[EngagementDetectionDecision]]
TopicLoader = Callable[[AsyncSession], Awaitable[list[EngagementTopic]]]
SampleLoader = Callable[..., Awaitable[list[DetectionMessage]]]
ContextLoader = Callable[..., Awaitable[CommunityContext]]
CandidateCreator = Callable[..., Awaitable[EngagementCandidateCreationResult]]
SemanticSelector = Callable[..., Awaitable[list[SemanticTriggerMatch]]]

__all__ = [name for name in globals() if not name.startswith("_") and name not in {"annotations"}]
