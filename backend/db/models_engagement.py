# ruff: noqa: F401,F403,F405
from __future__ import annotations

from backend.db.models_base import *

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
    source_message_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_reason: Mapped[str] = mapped_column(Text, nullable=False)
    moment_strength: Mapped[str] = mapped_column(Text, nullable=False)
    timeliness: Mapped[str] = mapped_column(Text, nullable=False)
    reply_value: Mapped[str] = mapped_column(Text, nullable=False)
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
    review_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reply_deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operator_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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

__all__ = [
    "CommunityEngagementSettings",
    "EngagementTarget",
    "CommunityAccountMembership",
    "EngagementTopic",
    "EngagementTopicEmbedding",
    "EngagementMessageEmbedding",
    "EngagementPromptProfile",
    "EngagementPromptProfileVersion",
    "EngagementStyleRule",
    "EngagementCandidate",
    "EngagementCandidateRevision",
    "EngagementAction",
]
