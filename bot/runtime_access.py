# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from .runtime_base import *

from .runtime_context import *
from .runtime_io import *


async def access_gate(update: Any, context: Any) -> None:
    settings: BotSettings = context.application.bot_data["settings"]
    if _is_identity_command(update) or _is_authorized_update(update, settings):
        _clear_pending_edit_if_command(update, context)
        return

    await _deny_access(update)
    from telegram.ext import ApplicationHandlerStop

    raise ApplicationHandlerStop


def _clear_pending_edit_if_command(update: Any, context: Any) -> None:
    command = _message_command_name(update)
    if command is None or command == "cancel_edit":
        return
    operator_id = _telegram_user_id(update)
    if operator_id is not None:
        _config_edit_store(context).cancel(operator_id)


def _is_authorized_update(update: Any, settings: BotSettings) -> bool:
    if not settings.allowed_user_ids:
        return True
    user_id = _telegram_user_id(update)
    return user_id in settings.allowed_user_ids if user_id is not None else False


def _is_engagement_admin(update: Any, context: Any) -> bool:
    return True


async def _require_engagement_admin(update: Any, context: Any) -> bool:
    return True


async def _is_engagement_admin_async(update: Any, context: Any) -> bool:
    return True


async def _backend_engagement_admin_capability(update: Any, context: Any) -> bool | None:
    user_id = _telegram_user_id(update)
    cached = _cached_backend_engagement_admin(update, context)
    if cached is not None:
        return cached

    try:
        data = await _api_client(context).get_operator_capabilities(user_id)
    except (AttributeError, BotApiError):
        return None

    if not data.get("backend_capabilities_available"):
        return None

    engagement_admin = data.get("engagement_admin")
    if not isinstance(engagement_admin, bool):
        return None

    if user_id is not None:
        _capability_cache(context)[user_id] = engagement_admin
    return engagement_admin


def _cached_backend_engagement_admin(update: Any, context: Any) -> bool | None:
    user_id = _telegram_user_id(update)
    if user_id is None:
        return None
    cached = _capability_cache(context).get(user_id)
    return cached if isinstance(cached, bool) else None


def _capability_cache(context: Any) -> dict[int, bool]:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None)
    if not isinstance(bot_data, dict):
        return {}
    cache = bot_data.get(OPERATOR_CAPABILITY_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        bot_data[OPERATOR_CAPABILITY_CACHE_KEY] = cache
    return cache


def _callback_action_requires_engagement_admin(action: str, parts: list[str]) -> bool:
    return False


def _is_identity_command(update: Any) -> bool:
    return _message_command_name(update) == "whoami"


def _message_command_name(update: Any) -> str | None:
    message = getattr(update, "message", None)
    text = getattr(message, "text", None)
    if not isinstance(text, str) or not text.startswith("/"):
        return None
    first_token = text.split(maxsplit=1)[0].lstrip("/")
    command = first_token.split("@", maxsplit=1)[0].lower()
    return command or None


def _telegram_user(update: Any) -> Any | None:
    effective_user = getattr(update, "effective_user", None)
    if effective_user is not None:
        return effective_user

    message = getattr(update, "message", None)
    message_user = getattr(message, "from_user", None)
    if message_user is not None:
        return message_user

    query = getattr(update, "callback_query", None)
    return getattr(query, "from_user", None)


def _telegram_user_id(update: Any) -> int | None:
    user = _telegram_user(update)
    raw_user_id = getattr(user, "id", None)
    if raw_user_id is None:
        return None
    try:
        return int(raw_user_id)
    except (TypeError, ValueError):
        return None


def _telegram_username(user: Any | None) -> str | None:
    username = getattr(user, "username", None)
    return username if isinstance(username, str) and username else None


def _reviewer_label(update: Any) -> str:
    user = _telegram_user(update)
    user_id = _telegram_user_id(update)
    if user_id is None:
        return "telegram_bot"
    username = _telegram_username(user)
    if username:
        return f"telegram:{user_id}:@{username}"
    return f"telegram:{user_id}"


async def _deny_access(update: Any) -> None:
    user = _telegram_user(update)
    user_id = _telegram_user_id(update)
    message = format_access_denied(user_id, username=_telegram_username(user))

    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.answer(message, show_alert=True)
        return

    await _reply(update, message)


def _looks_like_telegram_reference(raw_value: str) -> bool:
    value = raw_value.strip()
    if not value or any(character.isspace() for character in value):
        return False
    lowered = value.lower()
    return value.startswith("@") or lowered.startswith(("https://t.me/", "http://t.me/", "t.me/", "telegram.me/"))


__all__ = [
    "access_gate",
    "_clear_pending_edit_if_command",
    "_is_authorized_update",
    "_is_engagement_admin",
    "_require_engagement_admin",
    "_is_engagement_admin_async",
    "_backend_engagement_admin_capability",
    "_cached_backend_engagement_admin",
    "_capability_cache",
    "_callback_action_requires_engagement_admin",
    "_is_identity_command",
    "_message_command_name",
    "_telegram_user",
    "_telegram_user_id",
    "_telegram_username",
    "_reviewer_label",
    "_deny_access",
    "_looks_like_telegram_reference",
]
