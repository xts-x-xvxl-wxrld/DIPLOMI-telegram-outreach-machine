# ruff: noqa: F401,F403,F405
from __future__ import annotations

from backend.db.models_base import *

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

__all__ = [
    "SearchRun",
    "SearchQuery",
    "SearchCandidate",
    "SearchCandidateEvidence",
    "SearchReview",
]
