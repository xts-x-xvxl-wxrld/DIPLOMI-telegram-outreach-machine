from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.api.schemas import JobRef
from backend.db.enums import SearchAdapter, SearchReviewAction


class SearchRunCreateRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    requested_by: str | None = Field(default=None, min_length=1, max_length=200)
    language_hints: list[str] = Field(default_factory=list)
    locale_hints: list[str] = Field(default_factory=list)
    enabled_adapters: list[SearchAdapter] = Field(
        default_factory=lambda: [SearchAdapter.TELEGRAM_ENTITY_SEARCH]
    )
    per_run_candidate_cap: int = Field(default=100, ge=1, le=500)
    per_adapter_caps: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def query_must_have_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped


class SearchRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_query: str
    normalized_title: str
    requested_by: str | None = None
    status: str
    enabled_adapters: list[str]
    language_hints: list[str]
    locale_hints: list[str]
    per_run_candidate_cap: int
    per_adapter_caps: dict[str, Any]
    planner_source: str | None = None
    planner_metadata: dict[str, Any]
    ranking_version: str | None = None
    ranking_metadata: dict[str, Any]
    last_error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SearchRunCreateResponse(BaseModel):
    search_run: SearchRunOut
    job: JobRef


class SearchRunListItem(BaseModel):
    id: UUID
    raw_query: str
    normalized_title: str
    status: str
    query_count: int = 0
    candidate_count: int = 0
    promoted_count: int = 0
    rejected_count: int = 0
    last_error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class SearchRunListResponse(BaseModel):
    items: list[SearchRunListItem]
    limit: int
    offset: int
    total: int


class SearchRunCounts(BaseModel):
    queries: int = 0
    queries_completed: int = 0
    candidates: int = 0
    promoted: int = 0
    rejected: int = 0
    archived: int = 0


class SearchRunDetailResponse(BaseModel):
    search_run: SearchRunOut
    counts: SearchRunCounts


class SearchQueryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    search_run_id: UUID
    adapter: str
    query_text: str
    normalized_query_key: str
    language_hint: str | None = None
    locale_hint: str | None = None
    include_terms: list[str]
    exclusion_terms: list[str]
    status: str
    planner_source: str
    planner_metadata: dict[str, Any]
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class SearchQueryListResponse(BaseModel):
    items: list[SearchQueryOut]
    total: int


class SearchCandidateEvidenceSummaryOut(BaseModel):
    total: int = 0
    types: list[str] = Field(default_factory=list)
    snippets: list[str] = Field(default_factory=list)


class SearchCandidateListItem(BaseModel):
    id: UUID
    search_run_id: UUID
    status: str
    community_id: UUID | None = None
    title: str | None = None
    username: str | None = None
    telegram_url: str | None = None
    description: str | None = None
    member_count: int | None = None
    score: Decimal | None = None
    ranking_version: str | None = None
    score_components: dict[str, Any] = Field(default_factory=dict)
    evidence_summary: SearchCandidateEvidenceSummaryOut = Field(
        default_factory=SearchCandidateEvidenceSummaryOut
    )
    first_seen_at: datetime
    last_seen_at: datetime


class SearchCandidateListResponse(BaseModel):
    items: list[SearchCandidateListItem]
    limit: int
    offset: int
    total: int


class SearchCandidateReviewRequest(BaseModel):
    action: SearchReviewAction
    requested_by: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)


class SearchReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    search_run_id: UUID
    search_candidate_id: UUID
    community_id: UUID | None = None
    action: str
    scope: str
    requested_by: str | None = None
    notes: str | None = None
    created_at: datetime


class SearchCandidateReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    search_run_id: UUID
    status: str
    community_id: UUID | None = None
    reviewed_at: datetime | None = None
    last_reviewed_by: str | None = None


class SearchCandidateReviewResponse(BaseModel):
    candidate: SearchCandidateReviewOut
    review: SearchReviewOut
