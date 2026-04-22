# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from .runtime_base import *


def _api_client(context: Any) -> BotApiClient:
    return context.application.bot_data[API_CLIENT_KEY]


def _config_edit_store(context: Any) -> PendingEditStore:
    store = context.application.bot_data.get(CONFIG_EDIT_STORE_KEY)
    if store is None:
        store = PendingEditStore()
        context.application.bot_data[CONFIG_EDIT_STORE_KEY] = store
    return store


def _account_confirm_store(context: Any) -> dict[int, dict[str, Any]]:
    store = context.application.bot_data.get(ACCOUNT_CONFIRM_STORE_KEY)
    if store is None:
        store = {}
        context.application.bot_data[ACCOUNT_CONFIRM_STORE_KEY] = store
    return store


def _bot_settings(context: Any) -> BotSettings | None:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None)
    if not isinstance(bot_data, dict):
        return None
    settings = bot_data.get("settings")
    return settings if isinstance(settings, BotSettings) else None


__all__ = [
    "_api_client",
    "_config_edit_store",
    "_account_confirm_store",
    "_bot_settings",
]
