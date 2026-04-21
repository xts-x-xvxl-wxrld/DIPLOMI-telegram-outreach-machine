from __future__ import annotations

from enum import StrEnum


class CommunityStatus(StrEnum):
    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    MONITORING = "monitoring"
    DROPPED = "dropped"


class CommunitySource(StrEnum):
    MANUAL = "manual"
    EXPANSION = "expansion"
    WEB_SEARCH = "web_search"
    TELEGRAM_SEARCH = "telegram_search"


class SeedChannelStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    INVALID = "invalid"
    INACCESSIBLE = "inaccessible"
    NOT_COMMUNITY = "not_community"
    FAILED = "failed"


class TelegramEntityIntakeStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    INVALID = "invalid"
    INACCESSIBLE = "inaccessible"
    FAILED = "failed"


class TelegramEntityType(StrEnum):
    CHANNEL = "channel"
    GROUP = "group"
    USER = "user"
    BOT = "bot"


class SearchAdapter(StrEnum):
    TELEGRAM_ENTITY_SEARCH = "telegram_entity_search"


class SearchRunStatus(StrEnum):
    DRAFT = "draft"
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    RANKING = "ranking"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SearchQueryStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SearchCandidateStatus(StrEnum):
    CANDIDATE = "candidate"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    CONVERTED_TO_SEED = "converted_to_seed"


class SearchReviewAction(StrEnum):
    PROMOTE = "promote"
    REJECT = "reject"
    ARCHIVE = "archive"
    GLOBAL_REJECT = "global_reject"
    CONVERT_TO_SEED = "convert_to_seed"


class SearchReviewScope(StrEnum):
    RUN = "run"
    GLOBAL = "global"


class SearchEvidenceType(StrEnum):
    ENTITY_TITLE_MATCH = "entity_title_match"
    ENTITY_USERNAME_MATCH = "entity_username_match"
    DESCRIPTION_MATCH = "description_match"
    HANDLE_RESOLUTION = "handle_resolution"
    MANUAL_SEED = "manual_seed"
    LINKED_DISCUSSION = "linked_discussion"
    FORWARD_SOURCE = "forward_source"
    TELEGRAM_LINK = "telegram_link"
    MENTION = "mention"
    POST_TEXT_MATCH = "post_text_match"
    WEB_RESULT = "web_result"


class CollectionRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AccountStatus(StrEnum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    RATE_LIMITED = "rate_limited"
    BANNED = "banned"


class AccountPool(StrEnum):
    SEARCH = "search"
    ENGAGEMENT = "engagement"
    DISABLED = "disabled"


class ActivityStatus(StrEnum):
    INACTIVE = "inactive"
    PASSIVE = "passive"
    ACTIVE = "active"


class EngagementMode(StrEnum):
    DISABLED = "disabled"
    OBSERVE = "observe"
    SUGGEST = "suggest"
    REQUIRE_APPROVAL = "require_approval"
    AUTO_LIMITED = "auto_limited"


class EngagementTargetRefType(StrEnum):
    COMMUNITY_ID = "community_id"
    TELEGRAM_USERNAME = "telegram_username"
    TELEGRAM_LINK = "telegram_link"
    INVITE_LINK = "invite_link"


class EngagementTargetStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    ARCHIVED = "archived"


class CommunityAccountMembershipStatus(StrEnum):
    NOT_JOINED = "not_joined"
    JOIN_REQUESTED = "join_requested"
    JOINED = "joined"
    FAILED = "failed"
    LEFT = "left"
    BANNED = "banned"


class EngagementCandidateStatus(StrEnum):
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    EXPIRED = "expired"
    FAILED = "failed"


class EngagementActionType(StrEnum):
    JOIN = "join"
    REPLY = "reply"
    POST = "post"
    SKIP = "skip"


class EngagementActionStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class EngagementStyleRuleScope(StrEnum):
    GLOBAL = "global"
    ACCOUNT = "account"
    COMMUNITY = "community"
    TOPIC = "topic"
