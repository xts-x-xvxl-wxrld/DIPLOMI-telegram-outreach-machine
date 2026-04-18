from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class BotSettings:
    telegram_bot_token: str
    api_base_url: str
    api_token: str
    request_timeout_seconds: float = 15.0
    allowed_user_ids: frozenset[int] = frozenset()


def load_settings(env: Mapping[str, str] | None = None) -> BotSettings:
    values = env or os.environ
    return BotSettings(
        telegram_bot_token=values.get("TELEGRAM_BOT_TOKEN", ""),
        api_base_url=values.get("BOT_API_BASE_URL", "http://api:8000/api").rstrip("/"),
        api_token=values.get("BOT_API_TOKEN", ""),
        request_timeout_seconds=float(values.get("BOT_API_TIMEOUT_SECONDS", "15")),
        allowed_user_ids=parse_allowed_user_ids(values.get("TELEGRAM_ALLOWED_USER_IDS", "")),
    )


def validate_runtime_settings(settings: BotSettings) -> None:
    missing = []
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.api_token:
        missing.append("BOT_API_TOKEN")
    if missing:
        raise RuntimeError(f"Missing required bot setting(s): {', '.join(missing)}")


def parse_allowed_user_ids(raw_value: str) -> frozenset[int]:
    values: set[int] = set()
    for raw_item in raw_value.replace(",", " ").split():
        item = raw_item.strip()
        if not item:
            continue
        try:
            user_id = int(item)
        except ValueError as exc:
            raise ValueError(
                "TELEGRAM_ALLOWED_USER_IDS must contain only numeric Telegram user IDs"
            ) from exc
        if user_id <= 0:
            raise ValueError("TELEGRAM_ALLOWED_USER_IDS must contain positive Telegram user IDs")
        values.add(user_id)
    return frozenset(values)
