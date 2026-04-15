from __future__ import annotations

from enum import StrEnum


class CommunityStatus(StrEnum):
    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    MONITORING = "monitoring"
    DROPPED = "dropped"


class CommunitySource(StrEnum):
    TGSTAT = "tgstat"
    EXPANSION = "expansion"
    MANUAL = "manual"


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

