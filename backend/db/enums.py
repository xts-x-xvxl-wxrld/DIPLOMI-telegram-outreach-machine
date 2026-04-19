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
