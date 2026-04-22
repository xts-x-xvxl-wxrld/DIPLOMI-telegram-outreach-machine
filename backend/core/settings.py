from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/telegram_outreach",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://redis:6379/0", validation_alias="REDIS_URL")
    bot_api_token: str = Field(default="", validation_alias="BOT_API_TOKEN")
    engagement_admin_user_ids: str = Field(default="", validation_alias="ENGAGEMENT_ADMIN_USER_IDS")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_brief_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_BRIEF_MODEL")
    openai_engagement_model: str = Field(
        default="gpt-4o-mini",
        validation_alias="OPENAI_ENGAGEMENT_MODEL",
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias="OPENAI_EMBEDDING_MODEL",
    )
    openai_embedding_dimensions: int = Field(
        default=512,
        validation_alias="OPENAI_EMBEDDING_DIMENSIONS",
    )
    telegram_api_id: str = Field(default="", validation_alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(default="", validation_alias="TELEGRAM_API_HASH")
    sessions_dir: str = Field(default="/sessions", validation_alias="SESSIONS_DIR")
    telegram_member_import_limit: int = Field(
        default=10000,
        validation_alias="TELEGRAM_MEMBER_IMPORT_LIMIT",
    )
    community_snapshot_interval_minutes: int = Field(
        default=60,
        validation_alias="COMMUNITY_SNAPSHOT_INTERVAL_MINUTES",
    )
    engagement_detection_window_minutes: int = Field(
        default=60,
        validation_alias="ENGAGEMENT_DETECTION_WINDOW_MINUTES",
    )
    engagement_reply_deadline_minutes: int = Field(
        default=90,
        validation_alias="ENGAGEMENT_REPLY_DEADLINE_MINUTES",
    )
    engagement_scheduler_interval_seconds: int = Field(
        default=3600,
        validation_alias="ENGAGEMENT_SCHEDULER_INTERVAL_SECONDS",
    )
    engagement_semantic_matching_enabled: bool = Field(
        default=False,
        validation_alias="ENGAGEMENT_SEMANTIC_MATCHING_ENABLED",
    )
    engagement_semantic_match_threshold: float = Field(
        default=0.62,
        validation_alias="ENGAGEMENT_SEMANTIC_MATCH_THRESHOLD",
    )
    engagement_max_semantic_matches_per_topic: int = Field(
        default=3,
        validation_alias="ENGAGEMENT_MAX_SEMANTIC_MATCHES_PER_TOPIC",
    )
    engagement_max_embedding_messages_per_run: int = Field(
        default=100,
        validation_alias="ENGAGEMENT_MAX_EMBEDDING_MESSAGES_PER_RUN",
    )
    engagement_max_detector_calls_per_run: int = Field(
        default=5,
        validation_alias="ENGAGEMENT_MAX_DETECTOR_CALLS_PER_RUN",
    )
    engagement_message_embedding_retention_days: int = Field(
        default=14,
        validation_alias="ENGAGEMENT_MESSAGE_EMBEDDING_RETENTION_DAYS",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sync_database_url(self) -> str:
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
