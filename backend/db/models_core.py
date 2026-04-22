# ruff: noqa: F401,F403,F405
from __future__ import annotations

from backend.db.models_base import *

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

__all__ = [
    "AudienceBrief",
    "Community",
    "SeedGroup",
    "SeedChannel",
    "CommunityDiscoveryEdge",
    "TelegramEntityIntake",
    "CommunitySnapshot",
    "CollectionRun",
    "Message",
    "User",
    "CommunityMember",
    "AnalysisSummary",
    "TelegramAccount",
]
