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
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    tgstat_api_token: str = Field(default="", validation_alias="TGSTAT_API_TOKEN")
    telegram_api_id: str = Field(default="", validation_alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(default="", validation_alias="TELEGRAM_API_HASH")
    sessions_dir: str = Field(default="/sessions", validation_alias="SESSIONS_DIR")
    collection_interval_minutes: int = Field(
        default=60,
        validation_alias="COLLECTION_INTERVAL_MINUTES",
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

