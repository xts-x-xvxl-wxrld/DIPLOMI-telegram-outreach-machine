from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.db.enums import (
    CommunityStatus,
    EngagementMode,
    EngagementStyleRuleScope,
    EngagementTargetStatus,
)


class JobRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: str
    status: str

from backend.api.schemas_search import (  # noqa: E402,F401
    SearchCandidateEvidenceSummaryOut,
    SearchCandidateListItem,
    SearchCandidateListResponse,
    SearchCandidateReviewOut,
    SearchCandidateReviewRequest,
    SearchCandidateReviewResponse,
    SearchQueryListResponse,
    SearchQueryOut,
    SearchReviewOut,
    SearchRunCounts,
    SearchRunCreateRequest,
    SearchRunCreateResponse,
    SearchRunDetailResponse,
    SearchRunListItem,
    SearchRunListResponse,
    SearchRunOut,
)


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
    auto_expand: bool = False


class ExpansionJobRequest(BaseModel):
    community_ids: list[UUID]
    depth: int = Field(default=1, ge=1, le=3)


class SeedGroupExpansionJobRequest(BaseModel):
    brief_id: UUID | None = None
    depth: int = Field(default=1, ge=1, le=3)


class SeedGroupResolveJobRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)
    retry_failed: bool = False


class JobResponse(BaseModel):
    job: JobRef


class TelegramEntityIntakeRequest(BaseModel):
    handle: str = Field(min_length=1, max_length=256)
    requested_by: str | None = None


class TelegramEntityIntakeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_value: str
    normalized_key: str
    username: str
    telegram_url: str
    status: str
    entity_type: str | None = None
    community_id: UUID | None = None
    user_id: UUID | None = None
    requested_by: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TelegramEntityIntakeResponse(BaseModel):
    intake: TelegramEntityIntakeOut
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


class SeedImportRequest(BaseModel):
    csv_text: str = Field(min_length=1, max_length=500_000)
    file_name: str | None = None
    requested_by: str | None = None


class SeedImportErrorOut(BaseModel):
    row_number: int
    message: str


class SeedImportGroupSummaryOut(BaseModel):
    id: UUID
    name: str
    imported: int
    updated: int


class SeedImportResponse(BaseModel):
    imported: int
    updated: int
    errors: list[SeedImportErrorOut]
    groups: list[SeedImportGroupSummaryOut]


class SeedGroupListItem(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    created_by: str | None = None
    created_at: datetime
    seed_count: int
    resolved_count: int
    unresolved_count: int = 0
    failed_count: int = 0


class SeedGroupListResponse(BaseModel):
    items: list[SeedGroupListItem]
    total: int


class SeedGroupDetailResponse(BaseModel):
    group: SeedGroupListItem


class SeedChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_group_id: UUID
    raw_value: str
    username: str | None = None
    telegram_url: str | None = None
    title: str | None = None
    notes: str | None = None
    status: str
    community_id: UUID | None = None
    created_at: datetime


class SeedChannelListResponse(BaseModel):
    items: list[SeedChannelOut]
    total: int


class SeedGroupCandidateItem(BaseModel):
    community: CommunityOut
    seed_group_id: UUID
    source_seed_count: int
    evidence_count: int
    evidence_types: list[str]
    candidate_score: int


class SeedGroupCandidateListResponse(BaseModel):
    items: list[SeedGroupCandidateItem]
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


class CommunitySnapshotJobRequest(BaseModel):
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


class CommunityMemberOut(BaseModel):
    tg_user_id: int
    username: str | None = None
    first_name: str | None = None
    membership_status: str
    activity_status: str
    first_seen_at: datetime
    last_updated_at: datetime
    last_active_at: datetime | None = None


class CommunityMemberListResponse(BaseModel):
    items: list[CommunityMemberOut]
    limit: int
    offset: int
    total: int


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
    account_pool: str
    status: str
    flood_wait_until: datetime | None = None
    last_used_at: datetime | None = None
    last_error: str | None = None

class AccountDebugResponse(BaseModel):
    counts: dict[str, int]
    counts_by_pool: dict[str, int] = Field(default_factory=dict)
    items: list[AccountDebugItem]

class OperatorCapabilitiesOut(BaseModel):
    operator_user_id: int | None = None
    backend_capabilities_available: bool
    engagement_admin: bool | None = None
    source: str


class EngagementSettingsUpdate(BaseModel):
    mode: EngagementMode = EngagementMode.SUGGEST
    allow_join: bool = False
    allow_post: bool = False
    reply_only: bool = True
    require_approval: bool = True
    max_posts_per_day: int = Field(default=1, ge=0, le=3)
    min_minutes_between_posts: int = Field(default=240, ge=1)
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    assigned_account_id: UUID | None = None


class EngagementSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    community_id: UUID
    mode: str
    allow_join: bool
    allow_post: bool
    reply_only: bool
    require_approval: bool
    max_posts_per_day: int
    min_minutes_between_posts: int
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    assigned_account_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskFirstEngagementCreateRequest(BaseModel):
    target_id: UUID
    created_by: str = Field(min_length=1, max_length=200)


class TaskFirstEngagementPatchRequest(BaseModel):
    topic_id: UUID | None = None
    name: str | None = Field(default=None, max_length=200)


class TaskFirstEngagementSettingsUpdate(BaseModel):
    assigned_account_id: UUID | None = None
    mode: EngagementMode | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None


class TaskFirstWizardActionRequest(BaseModel):
    requested_by: str | None = Field(default=None, min_length=1, max_length=200)


class TaskFirstEngagementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    target_id: UUID
    community_id: UUID
    topic_id: UUID | None = None
    status: str
    name: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class TaskFirstEngagementSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    engagement_id: UUID
    assigned_account_id: UUID | None = None
    mode: str
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None


class TaskFirstEngagementCreateResponse(BaseModel):
    result: str
    engagement: TaskFirstEngagementOut


class TaskFirstEngagementPatchResponse(BaseModel):
    result: str
    engagement: TaskFirstEngagementOut | None = None
    message: str | None = None
    code: str | None = None


class TaskFirstEngagementSettingsResponse(BaseModel):
    result: str
    settings: TaskFirstEngagementSettingsOut | None = None
    message: str | None = None
    code: str | None = None


class TaskFirstWizardConfirmResponse(BaseModel):
    result: str
    message: str
    next_callback: str
    engagement_id: UUID | None = None
    engagement_status: str | None = None
    target_status: str | None = None
    field: str | None = None
    code: str | None = None


class TaskFirstWizardRetryResponse(BaseModel):
    result: str
    message: str
    next_callback: str
    engagement_id: UUID | None = None
    code: str | None = None


class CockpitHomeDraftPreviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    draft_id: UUID
    engagement_id: UUID
    text_preview: str
    target_label: str
    why: str
    updated: bool


class CockpitHomeIssuePreviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    issue_id: UUID
    engagement_id: UUID
    issue_type: str
    issue_label: str
    badge: str | None = None
    created_at: datetime


class CockpitHomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: str
    draft_count: int
    issue_count: int
    active_engagement_count: int
    has_sent_messages: bool
    next_draft_preview: CockpitHomeDraftPreviewOut | None = None
    latest_issue_preview: CockpitHomeIssuePreviewOut | None = None


class CockpitApprovalPlaceholderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slot: int
    label: str


class CockpitApprovalItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    draft_id: UUID
    engagement_id: UUID
    target_label: str
    text: str
    why: str
    badge: str | None = None


class CockpitApprovalQueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    queue_count: int
    updating_count: int
    empty_state: str
    placeholders: list[CockpitApprovalPlaceholderOut] = Field(default_factory=list)
    current: CockpitApprovalItemOut | None = None


class CockpitIssueActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_key: str
    label: str
    callback_family: str


class CockpitIssueItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    issue_id: UUID
    engagement_id: UUID
    issue_type: str
    issue_label: str
    badge: str | None = None
    created_at: datetime
    target_label: str
    context: str | None = None
    fix_actions: list[CockpitIssueActionOut] = Field(default_factory=list)
    candidate_id: UUID | None = None
    target_id: UUID | None = None
    community_id: UUID | None = None
    assigned_account_id: UUID | None = None


class CockpitIssueQueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    queue_count: int
    empty_state: str
    current: CockpitIssueItemOut | None = None


class CockpitPendingTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_kind: str
    label: str
    count: int
    resume_callback: str | None = None


class CockpitEngagementListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    engagement_id: UUID
    primary_label: str
    community_label: str
    sending_mode_label: str
    issue_count: int
    pending_task: CockpitPendingTaskOut | None = None
    created_at: datetime


class CockpitEngagementListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CockpitEngagementListItemOut]
    total: int
    offset: int
    limit: int


class CockpitEngagementDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    engagement_id: UUID
    target_label: str
    topic_label: str | None = None
    account_label: str | None = None
    sending_mode_label: str
    approval_count: int
    issue_count: int
    pending_task: CockpitPendingTaskOut | None = None


class CockpitSentItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_id: UUID
    message_text: str
    community_label: str
    sent_at: datetime


class CockpitSentFeedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CockpitSentItemOut]
    total: int
    offset: int
    limit: int


class CockpitDraftEditRequest(BaseModel):
    edit_request: str = Field(min_length=1, max_length=2000)
    requested_by: str | None = Field(default=None, min_length=1, max_length=200)


class CockpitDraftActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result: str
    message: str
    draft_id: UUID | None = None
    engagement_id: UUID | None = None
    next_callback: str | None = None
    code: str | None = None
    job_id: str | None = None
    job_type: str | None = None


class CockpitIssueActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result: str
    message: str
    next_callback: str | None = None
    code: str | None = None


class CockpitRateLimitDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result: str
    message: str
    next_callback: str
    issue_id: UUID | None = None
    engagement_id: UUID | None = None
    title: str | None = None
    target_label: str | None = None
    blocked_action_label: str | None = None
    scope_label: str | None = None
    reset_at: datetime | None = None


class CockpitQuietHoursReadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result: str
    message: str
    next_callback: str
    engagement_id: UUID | None = None
    title: str | None = None
    target_label: str | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None


class CockpitQuietHoursWriteRequest(BaseModel):
    quiet_hours_enabled: bool
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None


class CockpitQuietHoursWriteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result: str
    message: str
    next_callback: str
    engagement_id: UUID | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    code: str | None = None


class EngagementTargetCreateRequest(BaseModel):
    target_ref: str = Field(min_length=1, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
    added_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementTargetUpdateRequest(BaseModel):
    status: EngagementTargetStatus | None = None
    allow_join: bool | None = None
    allow_detect: bool | None = None
    allow_post: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)
    updated_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementTargetResolveJobRequest(BaseModel): requested_by: str | None = Field(default=None, min_length=1, max_length=200)  # noqa: E701
class EngagementCollectionJobRequest(BaseModel): window_days: int = Field(default=90, ge=1, le=365); requested_by: str | None = Field(default=None, min_length=1, max_length=200)  # noqa: E701,E702


class EngagementTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    community_id: UUID | None = None
    community_title: str | None = None
    submitted_ref: str
    submitted_ref_type: str
    status: str
    allow_join: bool
    allow_detect: bool
    allow_post: bool
    notes: str | None = None
    added_by: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class EngagementTargetListResponse(BaseModel):
    items: list[EngagementTargetOut]
    limit: int
    offset: int
    total: int


class EngagementTopicCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    stance_guidance: str = Field(min_length=1)
    trigger_keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    example_good_replies: list[str] = Field(default_factory=list)
    example_bad_replies: list[str] = Field(default_factory=list)
    active: bool = True


class EngagementTopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    stance_guidance: str | None = Field(default=None, min_length=1)
    trigger_keywords: list[str] | None = None
    negative_keywords: list[str] | None = None
    example_good_replies: list[str] | None = None
    example_bad_replies: list[str] | None = None
    active: bool | None = None


class EngagementTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    stance_guidance: str
    trigger_keywords: list[str]
    negative_keywords: list[str]
    example_good_replies: list[str]
    example_bad_replies: list[str]
    active: bool
    created_at: datetime
    updated_at: datetime


class EngagementTopicListResponse(BaseModel):
    items: list[EngagementTopicOut]


class EngagementTopicExampleCreateRequest(BaseModel):
    example_type: str = Field(pattern="^(good|bad)$")
    example: str = Field(min_length=1, max_length=800)


class EngagementPromptProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    active: bool = False
    model: str = Field(min_length=1, max_length=120)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_output_tokens: int = Field(default=1000, ge=128, le=4000)
    system_prompt: str = Field(min_length=1, max_length=12000)
    user_prompt_template: str = Field(min_length=1, max_length=24000)
    output_schema_name: str = Field(default="engagement_detection_v1", min_length=1, max_length=120)
    created_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementPromptProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    active: bool | None = None
    model: str | None = Field(default=None, min_length=1, max_length=120)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=128, le=4000)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=12000)
    user_prompt_template: str | None = Field(default=None, min_length=1, max_length=24000)
    output_schema_name: str | None = Field(default=None, min_length=1, max_length=120)
    updated_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementPromptProfileActivateRequest(BaseModel):
    updated_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementPromptProfileDuplicateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    created_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementPromptProfileRollbackRequest(BaseModel):
    version_id: UUID
    updated_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementPromptProfilePreviewRequest(BaseModel):
    variables: dict[str, Any] | None = None


class EngagementPromptProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    active: bool
    model: str
    temperature: float
    max_output_tokens: int
    system_prompt: str
    user_prompt_template: str
    output_schema_name: str
    current_version_number: int | None = None
    current_version_id: UUID | None = None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class EngagementPromptProfileListResponse(BaseModel):
    items: list[EngagementPromptProfileOut]
    limit: int
    offset: int
    total: int


class EngagementPromptProfileVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prompt_profile_id: UUID
    version_number: int
    model: str
    temperature: float
    max_output_tokens: int
    system_prompt: str
    user_prompt_template: str
    output_schema_name: str
    created_by: str
    created_at: datetime


class EngagementPromptProfileVersionListResponse(BaseModel):
    items: list[EngagementPromptProfileVersionOut]


class EngagementPromptPreviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: UUID | None = None
    profile_name: str
    version_id: UUID | None = None
    version_number: int | None = None
    model: str
    temperature: float
    max_output_tokens: int
    system_prompt: str
    rendered_user_prompt: str
    variables: dict[str, Any]


class EngagementStyleRuleCreateRequest(BaseModel):
    scope_type: EngagementStyleRuleScope = EngagementStyleRuleScope.GLOBAL
    scope_id: UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    rule_text: str = Field(min_length=1, max_length=4000)
    active: bool = True
    priority: int = Field(default=100, ge=0, le=1000)
    created_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementStyleRuleUpdateRequest(BaseModel):
    scope_type: EngagementStyleRuleScope | None = None
    scope_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    rule_text: str | None = Field(default=None, min_length=1, max_length=4000)
    active: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    updated_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementStyleRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope_type: str
    scope_id: UUID | None = None
    name: str
    rule_text: str
    active: bool
    priority: int
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class EngagementStyleRuleListResponse(BaseModel):
    items: list[EngagementStyleRuleOut]
    limit: int
    offset: int
    total: int


class EngagementCandidateEditRequest(BaseModel):
    final_reply: str = Field(min_length=1, max_length=800)
    edited_by: str | None = Field(default=None, min_length=1, max_length=200)
    edit_reason: str | None = Field(default=None, max_length=500)


class EngagementCandidateApproveRequest(BaseModel):
    final_reply: str | None = Field(default=None, max_length=800)
    reviewed_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementCandidateRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    reviewed_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementCandidateExpireRequest(BaseModel):
    expired_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementCandidateRetryRequest(BaseModel):
    retried_by: str | None = Field(default=None, min_length=1, max_length=200)

class EngagementDetectJobRequest(BaseModel):
    window_minutes: int = Field(default=60, ge=1, le=1440)
    requested_by: str | None = Field(default=None, min_length=1, max_length=200)

class EngagementJoinJobRequest(BaseModel):
    telegram_account_id: UUID | None = None
    requested_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementSendJobRequest(BaseModel):
    approved_by: str | None = Field(default=None, min_length=1, max_length=200)


class EngagementCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    community_id: UUID
    community_title: str | None = None
    topic_id: UUID
    topic_name: str
    source_tg_message_id: int | None = None; source_reply_to_tg_message_id: int | None = None  # noqa: E702
    source_excerpt: str | None = None; source_message_date: datetime | None = None  # noqa: E702
    opportunity_kind: str; root_candidate_id: UUID | None = None; conversation_key: str | None = None  # noqa: E702
    detected_at: datetime; detected_reason: str  # noqa: E702
    moment_strength: str; timeliness: str; reply_value: str  # noqa: E702
    suggested_reply: str | None = None
    final_reply: str | None = None
    prompt_profile_id: UUID | None = None; prompt_profile_version_id: UUID | None = None  # noqa: E702
    prompt_render_summary: dict[str, Any] | None = None
    risk_notes: list[str]
    status: str
    reviewed_by: str | None = None; reviewed_at: datetime | None = None  # noqa: E702
    review_deadline_at: datetime | None = None; reply_deadline_at: datetime  # noqa: E702
    operator_notified_at: datetime | None = None
    expires_at: datetime
    created_at: datetime


class EngagementCandidateListResponse(BaseModel):
    items: list[EngagementCandidateOut]
    limit: int
    offset: int
    total: int


class EngagementCandidateRevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    revision_number: int
    reply_text: str
    edited_by: str
    edit_reason: str | None = None
    created_at: datetime


class EngagementCandidateRevisionListResponse(BaseModel):
    items: list[EngagementCandidateRevisionOut]
    total: int


class EngagementActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID | None = None
    community_id: UUID
    telegram_account_id: UUID
    action_type: str
    status: str
    outbound_text: str | None = None
    reply_to_tg_message_id: int | None = None
    sent_tg_message_id: int | None = None
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class EngagementActionListResponse(BaseModel):
    items: list[EngagementActionOut]
    limit: int
    offset: int
    total: int


class EngagementSemanticRolloutBandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    min_similarity: float
    max_similarity: float
    total: int
    pending: int
    approved: int
    rejected: int
    expired: int
    approval_rate: float | None = None
    average_similarity: float | None = None


class EngagementSemanticRolloutSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    window_days: int
    community_id: UUID | None = None
    topic_id: UUID | None = None
    total_semantic_candidates: int
    reviewed_semantic_candidates: int
    pending: int
    approved: int
    rejected: int
    expired: int
    approval_rate: float | None = None
    bands: list[EngagementSemanticRolloutBandOut]
