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


class AudienceBrief(Base):
    __tablename__ = "audience_briefs"

    id: Mapped[uuid.UUID] = uuid_pk()
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(Text))
    related_phrases: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(Text))
    language_hints: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(Text))
    geography_hints: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(Text))
    exclusion_terms: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(Text))
    community_types: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    communities: Mapped[list["Community"]] = relationship(back_populates="brief")


class Community(Base):
    __tablename__ = "communities"
    __table_args__ = (
        Index("ix_communities_status", "status"),
        Index("ix_communities_brief_id", "brief_id"),
        Index("ix_communities_store_messages", "store_messages"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    member_count: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(Text)
    is_group: Mapped[bool | None] = mapped_column(Boolean)
    is_broadcast: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str | None] = mapped_column(Text)
    match_reason: Mapped[str | None] = mapped_column(Text)
    brief_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audience_briefs.id"))
    status: Mapped[str] = mapped_column(
        Text,
        default=CommunityStatus.CANDIDATE.value,
        server_default=CommunityStatus.CANDIDATE.value,
        nullable=False,
    )
    store_messages: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    brief: Mapped[AudienceBrief | None] = relationship(back_populates="communities")


class SeedGroup(Base):
    __tablename__ = "seed_groups"
    __table_args__ = (
        UniqueConstraint("normalized_name"),
        Index("ix_seed_groups_normalized_name", "normalized_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    channels: Mapped[list["SeedChannel"]] = relationship(back_populates="seed_group")


class SeedChannel(Base):
    __tablename__ = "seed_channels"
    __table_args__ = (
        UniqueConstraint("seed_group_id", "normalized_key"),
        Index("ix_seed_channels_seed_group_id", "seed_group_id"),
        Index("ix_seed_channels_status", "status"),
        Index("ix_seed_channels_community_id", "community_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    seed_group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seed_groups.id"), nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_key: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str | None] = mapped_column(Text)
    telegram_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text,
        default=SeedChannelStatus.PENDING.value,
        server_default=SeedChannelStatus.PENDING.value,
        nullable=False,
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communities.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    seed_group: Mapped[SeedGroup] = relationship(back_populates="channels")
    community: Mapped[Community | None] = relationship()


class CommunityDiscoveryEdge(Base):
    __tablename__ = "community_discovery_edges"
    __table_args__ = (
        UniqueConstraint(
            "seed_group_id",
            "seed_channel_id",
            "source_community_id",
            "target_community_id",
            "evidence_type",
            "evidence_value",
            name="uq_community_discovery_edges_identity",
        ),
        Index("ix_community_discovery_edges_seed_group_id", "seed_group_id"),
        Index("ix_community_discovery_edges_seed_channel_id", "seed_channel_id"),
        Index("ix_community_discovery_edges_source_community_id", "source_community_id"),
        Index("ix_community_discovery_edges_target_community_id", "target_community_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    seed_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seed_groups.id"))
    seed_channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seed_channels.id"))
    source_community_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communities.id"))
    target_community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    seed_group: Mapped[SeedGroup | None] = relationship()
    seed_channel: Mapped[SeedChannel | None] = relationship()
    source_community: Mapped[Community | None] = relationship(foreign_keys=[source_community_id])
    target_community: Mapped[Community] = relationship(foreign_keys=[target_community_id])


class TelegramEntityIntake(Base):
    __tablename__ = "telegram_entity_intakes"
    __table_args__ = (
        UniqueConstraint("normalized_key"),
        Index("ix_telegram_entity_intakes_status", "status"),
        Index("ix_telegram_entity_intakes_entity_type", "entity_type"),
        Index("ix_telegram_entity_intakes_community_id", "community_id"),
        Index("ix_telegram_entity_intakes_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_key: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        default=TelegramEntityIntakeStatus.PENDING.value,
        server_default=TelegramEntityIntakeStatus.PENDING.value,
        nullable=False,
    )
    entity_type: Mapped[str | None] = mapped_column(Text)
    community_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communities.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    requested_by: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    community: Mapped[Community | None] = relationship()
    user: Mapped["User | None"] = relationship()


class SearchRun(Base):
    __tablename__ = "search_runs"
    __table_args__ = (
        Index("ix_search_runs_status_created", "status", "created_at"),
        Index("ix_search_runs_requested_by_created", "requested_by", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_title: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text,
        default=SearchRunStatus.DRAFT.value,
        server_default=SearchRunStatus.DRAFT.value,
        nullable=False,
    )
    enabled_adapters: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        default=lambda: [SearchAdapter.TELEGRAM_ENTITY_SEARCH.value],
        server_default=text("'{telegram_entity_search}'::text[]"),
        nullable=False,
    )
    language_hints: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        default=list,
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    locale_hints: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        default=list,
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    per_run_candidate_cap: Mapped[int] = mapped_column(
        Integer,
        default=100,
        server_default="100",
        nullable=False,
    )
    per_adapter_caps: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    planner_source: Mapped[str | None] = mapped_column(Text)
    planner_metadata: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    ranking_version: Mapped[str | None] = mapped_column(Text)
    ranking_metadata: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    queries: Mapped[list["SearchQuery"]] = relationship(
        back_populates="search_run",
        cascade="all, delete-orphan",
    )
    candidates: Mapped[list["SearchCandidate"]] = relationship(
        back_populates="search_run",
        cascade="all, delete-orphan",
    )
    reviews: Mapped[list["SearchReview"]] = relationship(
        back_populates="search_run",
        cascade="all, delete-orphan",
    )


class SearchQuery(Base):
    __tablename__ = "search_queries"
    __table_args__ = (
        UniqueConstraint(
            "search_run_id",
            "adapter",
            "normalized_query_key",
            name="uq_search_queries_run_adapter_key",
        ),
        Index("ix_search_queries_run_status", "search_run_id", "status"),
        Index("ix_search_queries_adapter_status", "adapter", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    adapter: Mapped[str] = mapped_column(Text, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query_key: Mapped[str] = mapped_column(Text, nullable=False)
    language_hint: Mapped[str | None] = mapped_column(Text)
    locale_hint: Mapped[str | None] = mapped_column(Text)
    include_terms: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        default=list,
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    exclusion_terms: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        default=list,
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        default=SearchQueryStatus.PENDING.value,
        server_default=SearchQueryStatus.PENDING.value,
        nullable=False,
    )
    planner_source: Mapped[str] = mapped_column(
        Text,
        default="deterministic_v1",
        server_default="deterministic_v1",
        nullable=False,
    )
    planner_metadata: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    search_run: Mapped[SearchRun] = relationship(back_populates="queries")


class SearchCandidate(Base):
    __tablename__ = "search_candidates"
    __table_args__ = (
        Index("ix_search_candidates_run_status", "search_run_id", "status"),
        Index("ix_search_candidates_community_id", "community_id"),
        Index("ix_search_candidates_score", "score"),
        Index(
            "uq_search_candidates_run_community",
            "search_run_id",
            "community_id",
            unique=True,
            postgresql_where=text("community_id IS NOT NULL"),
        ),
        Index(
            "uq_search_candidates_run_username",
            "search_run_id",
            "normalized_username",
            unique=True,
            postgresql_where=text("normalized_username IS NOT NULL"),
        ),
        Index(
            "uq_search_candidates_run_canonical_url",
            "search_run_id",
            "canonical_url",
            unique=True,
            postgresql_where=text("canonical_url IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communities.id"))
    status: Mapped[str] = mapped_column(
        Text,
        default=SearchCandidateStatus.CANDIDATE.value,
        server_default=SearchCandidateStatus.CANDIDATE.value,
        nullable=False,
    )
    normalized_username: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    raw_title: Mapped[str | None] = mapped_column(Text)
    raw_description: Mapped[str | None] = mapped_column(Text)
    raw_member_count: Mapped[int | None] = mapped_column(Integer)
    adapter_first_seen: Mapped[str | None] = mapped_column(Text)
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    score_components: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    ranking_version: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_reviewed_by: Mapped[str | None] = mapped_column(Text)

    search_run: Mapped[SearchRun] = relationship(back_populates="candidates")
    community: Mapped[Community | None] = relationship()
    evidence: Mapped[list["SearchCandidateEvidence"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    reviews: Mapped[list["SearchReview"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class SearchCandidateEvidence(Base):
    __tablename__ = "search_candidate_evidence"
    __table_args__ = (
        Index("ix_search_candidate_evidence_candidate_captured", "search_candidate_id", "captured_at"),
        Index("ix_search_candidate_evidence_run_type", "search_run_id", "evidence_type"),
        Index("ix_search_candidate_evidence_community_id", "community_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    search_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communities.id"))
    search_query_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("search_queries.id", ondelete="SET NULL"),
    )
    adapter: Mapped[str] = mapped_column(Text, nullable=False)
    query_text: Mapped[str | None] = mapped_column(Text)
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_value: Mapped[str | None] = mapped_column(Text)
    evidence_metadata: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    source_community_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communities.id"))
    source_seed_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seed_groups.id"))
    source_seed_channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seed_channels.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    search_run: Mapped[SearchRun] = relationship()
    candidate: Mapped[SearchCandidate] = relationship(back_populates="evidence")
    community: Mapped[Community | None] = relationship(foreign_keys=[community_id])
    search_query: Mapped[SearchQuery | None] = relationship()
    source_community: Mapped[Community | None] = relationship(foreign_keys=[source_community_id])
    source_seed_group: Mapped[SeedGroup | None] = relationship()
    source_seed_channel: Mapped[SeedChannel | None] = relationship()


class SearchReview(Base):
    __tablename__ = "search_reviews"
    __table_args__ = (
        Index("ix_search_reviews_candidate_created", "search_candidate_id", "created_at"),
        Index("ix_search_reviews_run_action", "search_run_id", "action"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    search_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communities.id"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(
        Text,
        default=SearchReviewScope.RUN.value,
        server_default=SearchReviewScope.RUN.value,
        nullable=False,
    )
    requested_by: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    review_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        postgresql.JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    search_run: Mapped[SearchRun] = relationship(back_populates="reviews")
    candidate: Mapped[SearchCandidate] = relationship(back_populates="reviews")
    community: Mapped[Community | None] = relationship()


class CommunitySnapshot(Base):
    __tablename__ = "community_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"))
    member_count: Mapped[int | None] = mapped_column(Integer)
    message_count_7d: Mapped[int | None] = mapped_column(Integer)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        Index("ix_collection_runs_community_started", "community_id", "started_at"),
        Index("ix_collection_runs_analysis_status", "analysis_status"),
        Index("ix_collection_runs_analysis_input_expires", "analysis_input_expires_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"))
    brief_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audience_briefs.id"))
    status: Mapped[str] = mapped_column(
        Text,
        default=CollectionRunStatus.RUNNING.value,
        server_default=CollectionRunStatus.RUNNING.value,
        nullable=False,
    )
    analysis_status: Mapped[str] = mapped_column(
        Text,
        default=AnalysisStatus.PENDING.value,
        server_default=AnalysisStatus.PENDING.value,
        nullable=False,
    )
    window_days: Mapped[int] = mapped_column(Integer, default=90, server_default="90", nullable=False)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    messages_seen: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    members_seen: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    activity_events: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("community_snapshots.id"))
    analysis_input: Mapped[dict[str, Any] | None] = mapped_column(postgresql.JSONB)
    analysis_input_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("community_id", "tg_message_id"),
        Index("ix_messages_community_message_date", "community_id", "message_date"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tg_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"))
    sender_user_id: Mapped[int | None] = mapped_column(BigInteger)
    message_type: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    has_forward: Mapped[bool | None] = mapped_column(Boolean, default=False, server_default="false")
    forward_from_id: Mapped[int | None] = mapped_column(BigInteger)
    reply_to_message_id: Mapped[int | None] = mapped_column(BigInteger)
    views: Mapped[int | None] = mapped_column(Integer)
    reactions_count: Mapped[int | None] = mapped_column(Integer)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    message_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_tg_user_id", "tg_user_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommunityMember(Base):
    __tablename__ = "community_members"
    __table_args__ = (
        UniqueConstraint("community_id", "user_id"),
        Index("ix_community_members_activity", "community_id", "activity_status"),
        Index("ix_community_members_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    activity_status: Mapped[str] = mapped_column(
        Text,
        default=ActivityStatus.INACTIVE.value,
        server_default=ActivityStatus.INACTIVE.value,
        nullable=False,
    )
    event_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnalysisSummary(Base):
    __tablename__ = "analysis_summaries"
    __table_args__ = (Index("ix_analysis_summaries_community_analyzed", "community_id", "analyzed_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"))
    brief_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audience_briefs.id"))
    summary: Mapped[str | None] = mapped_column(Text)
    dominant_themes: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(Text))
    activity_level: Mapped[str | None] = mapped_column(Text)
    is_broadcast: Mapped[bool | None] = mapped_column(Boolean)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    relevance_notes: Mapped[str | None] = mapped_column(Text)
    centrality: Mapped[str | None] = mapped_column(Text)
    analysis_window_days: Mapped[int | None] = mapped_column(Integer, default=90, server_default="90")
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    model: Mapped[str | None] = mapped_column(Text)


class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"
    __table_args__ = (
        Index("ix_telegram_accounts_status", "status"),
        Index("ix_telegram_accounts_pool_status_last_used", "account_pool", "status", "last_used_at"),
        Index("ix_telegram_accounts_lease_expires", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    phone: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    session_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    account_pool: Mapped[str] = mapped_column(
        Text,
        default=AccountPool.SEARCH.value,
        server_default=AccountPool.SEARCH.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        default=AccountStatus.AVAILABLE.value,
        server_default=AccountStatus.AVAILABLE.value,
        nullable=False,
    )
    flood_wait_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class CommunityEngagementSettings(Base):
    __tablename__ = "community_engagement_settings"
    __table_args__ = (
        UniqueConstraint("community_id"),
        Index("ix_community_engagement_settings_community_id", "community_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"), nullable=False)
    mode: Mapped[str] = mapped_column(
        Text,
        default=EngagementMode.SUGGEST.value,
        server_default=EngagementMode.SUGGEST.value,
        nullable=False,
    )
    allow_join: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    allow_post: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    reply_only: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    require_approval: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    max_posts_per_day: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    min_minutes_between_posts: Mapped[int] = mapped_column(Integer, default=240, server_default="240", nullable=False)
    quiet_hours_start: Mapped[time | None] = mapped_column(Time(timezone=False))
    quiet_hours_end: Mapped[time | None] = mapped_column(Time(timezone=False))
    assigned_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("telegram_accounts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    community: Mapped[Community] = relationship()
    assigned_account: Mapped[TelegramAccount | None] = relationship()


class EngagementTarget(Base):
    __tablename__ = "engagement_targets"
    __table_args__ = (
        UniqueConstraint("community_id"),
        Index("ix_engagement_targets_community_id", "community_id"),
        Index("ix_engagement_targets_status", "status"),
        Index("ix_engagement_targets_submitted_ref", "submitted_ref"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communities.id"))
    submitted_ref: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_ref_type: Mapped[str] = mapped_column(
        Text,
        default=EngagementTargetRefType.TELEGRAM_USERNAME.value,
        server_default=EngagementTargetRefType.TELEGRAM_USERNAME.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        default=EngagementTargetStatus.PENDING.value,
        server_default=EngagementTargetStatus.PENDING.value,
        nullable=False,
    )
    allow_join: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    allow_detect: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    allow_post: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    added_by: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    community: Mapped[Community | None] = relationship()


class CommunityAccountMembership(Base):
    __tablename__ = "community_account_memberships"
    __table_args__ = (
        UniqueConstraint("community_id", "telegram_account_id"),
        Index(
            "ix_community_account_memberships_community_account",
            "community_id",
            "telegram_account_id",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"), nullable=False)
    telegram_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("telegram_accounts.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        default=CommunityAccountMembershipStatus.NOT_JOINED.value,
        server_default=CommunityAccountMembershipStatus.NOT_JOINED.value,
        nullable=False,
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    community: Mapped[Community] = relationship()
    telegram_account: Mapped[TelegramAccount] = relationship()


class EngagementTopic(Base):
    __tablename__ = "engagement_topics"
    __table_args__ = (Index("ix_engagement_topics_active", "active"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    stance_guidance: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_keywords: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        default=list,
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    negative_keywords: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        default=list,
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    example_good_replies: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        default=list,
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    example_bad_replies: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        default=list,
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EngagementTopicEmbedding(Base):
    __tablename__ = "engagement_topic_embeddings"
    __table_args__ = (
        UniqueConstraint("topic_id", "model", "dimensions", "profile_text_hash"),
        Index("ix_engagement_topic_embeddings_topic_id", "topic_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagement_topics.id"), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(postgresql.JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    topic: Mapped[EngagementTopic] = relationship()


class EngagementMessageEmbedding(Base):
    __tablename__ = "engagement_message_embeddings"
    __table_args__ = (
        UniqueConstraint("community_id", "tg_message_id", "source_text_hash", "model", "dimensions"),
        Index(
            "ix_engagement_message_embeddings_lookup",
            "community_id",
            "source_text_hash",
            "model",
            "dimensions",
        ),
        Index("ix_engagement_message_embeddings_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"), nullable=False)
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger)
    source_text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(postgresql.JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    community: Mapped[Community] = relationship()


class EngagementPromptProfile(Base):
    __tablename__ = "engagement_prompt_profiles"
    __table_args__ = (
        Index("ix_engagement_prompt_profiles_active", "active"),
        Index("ix_engagement_prompt_profiles_updated", "updated_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.2"), server_default="0.2", nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000", nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_name: Mapped[str] = mapped_column(
        Text,
        default="engagement_detection_v1",
        server_default="engagement_detection_v1",
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    versions: Mapped[list["EngagementPromptProfileVersion"]] = relationship(
        back_populates="prompt_profile",
        cascade="all, delete-orphan",
    )


class EngagementPromptProfileVersion(Base):
    __tablename__ = "engagement_prompt_profile_versions"
    __table_args__ = (
        UniqueConstraint("prompt_profile_id", "version_number"),
        Index("ix_engagement_prompt_profile_versions_profile", "prompt_profile_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    prompt_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagement_prompt_profiles.id"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    prompt_profile: Mapped[EngagementPromptProfile] = relationship(back_populates="versions")


class EngagementStyleRule(Base):
    __tablename__ = "engagement_style_rules"
    __table_args__ = (
        Index("ix_engagement_style_rules_scope", "scope_type", "scope_id", "active", "priority"),
        Index("ix_engagement_style_rules_active", "active"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    scope_type: Mapped[str] = mapped_column(
        Text,
        default=EngagementStyleRuleScope.GLOBAL.value,
        server_default=EngagementStyleRuleScope.GLOBAL.value,
        nullable=False,
    )
    scope_id: Mapped[uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EngagementCandidate(Base):
    __tablename__ = "engagement_candidates"
    __table_args__ = (
        Index("ix_engagement_candidates_status_created", "status", "created_at"),
        Index("ix_engagement_candidates_community_topic_status", "community_id", "topic_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"), nullable=False)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagement_topics.id"), nullable=False)
    source_tg_message_id: Mapped[int | None] = mapped_column(BigInteger)
    source_excerpt: Mapped[str | None] = mapped_column(Text)
    detected_reason: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_reply: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    model_output: Mapped[dict[str, Any] | None] = mapped_column(postgresql.JSONB)
    prompt_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("engagement_prompt_profiles.id"))
    prompt_profile_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("engagement_prompt_profile_versions.id")
    )
    prompt_render_summary: Mapped[dict[str, Any] | None] = mapped_column(postgresql.JSONB)
    risk_notes: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        default=list,
        server_default=text("'{}'::text[]"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        default=EngagementCandidateStatus.NEEDS_REVIEW.value,
        server_default=EngagementCandidateStatus.NEEDS_REVIEW.value,
        nullable=False,
    )
    final_reply: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    community: Mapped[Community] = relationship()
    topic: Mapped[EngagementTopic] = relationship()
    prompt_profile: Mapped[EngagementPromptProfile | None] = relationship(foreign_keys=[prompt_profile_id])
    prompt_profile_version: Mapped[EngagementPromptProfileVersion | None] = relationship(
        foreign_keys=[prompt_profile_version_id]
    )


class EngagementCandidateRevision(Base):
    __tablename__ = "engagement_candidate_revisions"
    __table_args__ = (
        UniqueConstraint("candidate_id", "revision_number"),
        Index("ix_engagement_candidate_revisions_candidate", "candidate_id", "revision_number"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagement_candidates.id"), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    edited_by: Mapped[str] = mapped_column(Text, nullable=False)
    edit_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    candidate: Mapped[EngagementCandidate] = relationship()


class EngagementAction(Base):
    __tablename__ = "engagement_actions"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        Index("ix_engagement_actions_community_created", "community_id", "created_at"),
        Index("ix_engagement_actions_account_created", "telegram_account_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("engagement_candidates.id"))
    community_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communities.id"), nullable=False)
    telegram_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("telegram_accounts.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(
        Text,
        default=EngagementActionType.REPLY.value,
        server_default=EngagementActionType.REPLY.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        default=EngagementActionStatus.QUEUED.value,
        server_default=EngagementActionStatus.QUEUED.value,
        nullable=False,
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    outbound_text: Mapped[str | None] = mapped_column(Text)
    reply_to_tg_message_id: Mapped[int | None] = mapped_column(BigInteger)
    sent_tg_message_id: Mapped[int | None] = mapped_column(BigInteger)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    candidate: Mapped[EngagementCandidate | None] = relationship()
    community: Mapped[Community] = relationship()
    telegram_account: Mapped[TelegramAccount] = relationship()
