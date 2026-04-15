from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.db.enums import CommunityStatus


class JobRef(BaseModel):
    id: str
    type: str
    status: str


class AudienceBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_input: str
    keywords: list[str] | None = None
    related_phrases: list[str] | None = None
    language_hints: list[str] | None = None
    geography_hints: list[str] | None = None
    exclusion_terms: list[str] | None = None
    community_types: list[str] | None = None
    created_at: datetime


class CreateBriefRequest(BaseModel):
    raw_input: str = Field(min_length=1)
    auto_start_discovery: bool = True


class CreateBriefResponse(BaseModel):
    brief: AudienceBriefOut
    job: JobRef | None


class BriefCounts(BaseModel):
    candidate: int = 0
    approved: int = 0
    rejected: int = 0
    monitoring: int = 0


class BriefDetailResponse(BaseModel):
    brief: AudienceBriefOut
    counts: BriefCounts


class DiscoveryJobRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    auto_expand: bool = True


class ExpansionJobRequest(BaseModel):
    community_ids: list[UUID]
    depth: int = Field(default=1, ge=1, le=3)


class JobResponse(BaseModel):
    job: JobRef


class CommunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tg_id: int
    username: str | None = None
    title: str | None = None
    description: str | None = None
    member_count: int | None = None
    language: str | None = None
    is_group: bool | None = None
    is_broadcast: bool | None = None
    source: str | None = None
    match_reason: str | None = None
    brief_id: UUID | None = None
    status: str
    store_messages: bool
    first_seen_at: datetime
    last_snapshot_at: datetime | None = None


class CommunityListResponse(BaseModel):
    items: list[CommunityOut]
    limit: int
    offset: int
    total: int


class ReviewCommunityRequest(BaseModel):
    decision: str
    store_messages: bool = False


class ReviewCommunityResponse(BaseModel):
    community: CommunityOut
    job: JobRef | None


class PatchCommunityRequest(BaseModel):
    status: CommunityStatus | None = None
    store_messages: bool | None = None


class PatchCommunityResponse(BaseModel):
    community: CommunityOut


class CommunityDetailResponse(BaseModel):
    community: CommunityOut
    latest_snapshot: dict[str, Any] | None
    latest_analysis: dict[str, Any] | None


class CollectionJobRequest(BaseModel):
    window_days: int = Field(default=90, ge=1, le=365)


class CollectionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    community_id: UUID
    status: str
    analysis_status: str
    window_days: int
    messages_seen: int
    members_seen: int
    started_at: datetime
    completed_at: datetime | None = None


class CollectionRunListResponse(BaseModel):
    items: list[CollectionRunOut]


class AnalysisSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    community_id: UUID
    brief_id: UUID | None = None
    summary: str | None = None
    dominant_themes: list[str] | None = None
    activity_level: str | None = None
    is_broadcast: bool | None = None
    relevance_score: Decimal | None = None
    relevance_notes: str | None = None
    centrality: str | None = None
    analysis_window_days: int | None = None
    analyzed_at: datetime
    model: str | None = None


class AnalysisListResponse(BaseModel):
    items: list[AnalysisSummaryOut]


class JobStatusResponse(BaseModel):
    id: str
    type: str | None
    status: str
    meta: dict[str, Any]
    error: str | None
    created_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None


class AccountDebugItem(BaseModel):
    id: UUID
    phone: str
    status: str
    flood_wait_until: datetime | None = None
    last_used_at: datetime | None = None
    last_error: str | None = None


class AccountDebugResponse(BaseModel):
    counts: dict[str, int]
    items: list[AccountDebugItem]
