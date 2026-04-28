# ruff: noqa: F401,F403,F405
from __future__ import annotations

import uuid
from datetime import datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.db.enums import (
    AccountPool,
    AccountStatus,
    ActivityStatus,
    AnalysisStatus,
    CollectionRunStatus,
    CommunityAccountMembershipStatus,
    CommunityStatus,
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementStatus,
    EngagementStyleRuleScope,
    EngagementTargetRefType,
    EngagementTargetStatus,
    SeedChannelStatus,
    SearchAdapter,
    SearchCandidateStatus,
    SearchQueryStatus,
    SearchReviewScope,
    SearchRunStatus,
    TelegramEntityIntakeStatus,
)

def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

__all__ = [name for name in globals() if not name.startswith("_") and name not in {"annotations"}]
