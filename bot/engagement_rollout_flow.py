from __future__ import annotations

from typing import Any

from bot.api_client import BotApiError
from bot.formatting import format_api_error, format_engagement_semantic_rollout
from bot.ui import engagement_rollout_markup


async def _send_engagement_rollout(update: Any, context: Any, *, window_days: int = 14) -> None:
    client = _api_client(context)
    try:
        data = await client.get_engagement_semantic_rollout(window_days=window_days)
    except BotApiError as exc:
        await _callback_reply(update, format_api_error(exc.message))
        return
    await _callback_reply(
        update,
        format_engagement_semantic_rollout(data),
        reply_markup=engagement_rollout_markup(window_days=window_days),
    )


from .runtime import _api_client, _callback_reply  # noqa: E402


__all__ = ["_send_engagement_rollout"]
