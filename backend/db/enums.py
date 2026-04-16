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
