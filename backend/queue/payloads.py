from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BriefProcessPayload(BaseModel):
    brief_id: UUID
    requested_by: str
    auto_start_discovery: bool = True


class DiscoveryPayload(BaseModel):
    brief_id: UUID
    requested_by: str
    limit: int = Field(default=50, ge=1)
    auto_expand: bool = False


class SeedResolvePayload(BaseModel):
    seed_group_id: UUID
    requested_by: str
    limit: int = Field(default=100, ge=1, le=1000)
    retry_failed: bool = False


class SeedExpandPayload(BaseModel):
    seed_group_id: UUID
    brief_id: UUID | None = None
    depth: int = Field(default=1, ge=1)
    requested_by: str


class TelegramEntityResolvePayload(BaseModel):
    intake_id: UUID
    requested_by: str


class SearchPlanPayload(BaseModel):
    search_run_id: UUID
    requested_by: str | None = None


class SearchRankPayload(BaseModel):
    search_run_id: UUID
    requested_by: str | None = None


class ExpansionPayload(BaseModel):
    brief_id: UUID | None = None
    community_ids: list[UUID]
    depth: int = Field(default=1, ge=1)
    requested_by: str


class CommunitySnapshotPayload(BaseModel):
    community_id: UUID
    reason: Literal["manual", "initial"]
    requested_by: str | None = None
    window_days: int = Field(default=90, ge=1)


class CollectionPayload(BaseModel):
    community_id: UUID
    reason: Literal["engagement", "scheduled", "manual"]
    requested_by: str | None = None
    window_days: int = Field(default=90, ge=1)


class AnalysisPayload(BaseModel):
    collection_run_id: UUID
    requested_by: str | None = None


class CommunityJoinPayload(BaseModel):
    community_id: UUID
    telegram_account_id: UUID | None = None
    requested_by: str


class EngagementTargetResolvePayload(BaseModel):
    target_id: UUID
    requested_by: str


class EngagementDetectPayload(BaseModel):
    community_id: UUID
    collection_run_id: UUID | None = None
    window_minutes: int = Field(default=60, ge=1)
    requested_by: str | None = None


class EngagementSendPayload(BaseModel):
    candidate_id: UUID
    approved_by: str
