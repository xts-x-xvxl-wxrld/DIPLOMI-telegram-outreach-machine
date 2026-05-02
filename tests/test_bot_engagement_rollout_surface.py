from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.callback_handlers import callback_query
from bot.main import API_CLIENT_KEY
from bot.ui import (
    ACTION_ENGAGEMENT_ADMIN_ADVANCED,
    ACTION_ENGAGEMENT_ROLLOUT,
    engagement_admin_advanced_markup,
    engagement_rollout_markup,
    parse_callback_data,
)


class _FakeMessage:
    def __init__(self) -> None:
        self.replies: list[dict[str, Any]] = []

    async def reply_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.replies.append({"text": text, "reply_markup": reply_markup})


class _FakeCallbackQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = _FakeMessage()
        self.from_user = SimpleNamespace(id=123, username="operator")
        self.answers: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append({"text": text, "show_alert": show_alert})

    async def edit_message_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.edits.append({"text": text, "reply_markup": reply_markup})


class _FakeApiClient:
    def __init__(self) -> None:
        self.rollout_calls: list[dict[str, Any]] = []

    async def get_engagement_semantic_rollout(self, *, window_days: int = 14) -> dict[str, Any]:
        self.rollout_calls.append({"window_days": window_days})
        return {
            "window_days": window_days,
            "overall": {"total": 2, "approved": 1, "rejected": 1, "pending": 0, "expired": 0},
            "bands": [
                {
                    "label": "0.80-0.89",
                    "total": 1,
                    "approved": 1,
                    "rejected": 0,
                    "pending": 0,
                    "expired": 0,
                    "approval_rate": 1.0,
                    "average_similarity": 0.84,
                }
            ],
        }


def _callback_update(data: str) -> Any:
    query = _FakeCallbackQuery(data)
    return SimpleNamespace(
        message=None,
        callback_query=query,
        effective_user=SimpleNamespace(id=123, username="operator"),
    )


def _context(client: _FakeApiClient | None = None) -> Any:
    app_data: dict[str, Any] = {}
    if client is not None:
        app_data[API_CLIENT_KEY] = client
    return SimpleNamespace(args=[], application=SimpleNamespace(bot_data=app_data), user_data={})


def _labels(markup: Any) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


def _callbacks(markup: Any) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_engagement_admin_advanced_markup_exposes_semantic_rollout_button() -> None:
    markup = engagement_admin_advanced_markup()

    assert f"{ACTION_ENGAGEMENT_ROLLOUT}:14" in _callbacks(markup)
    assert "📊 Semantic rollout" in _labels(markup)


def test_engagement_rollout_markup_exposes_window_shortcuts_and_navigation() -> None:
    markup = engagement_rollout_markup(window_days=14)
    callbacks = _callbacks(markup)
    labels = _labels(markup)

    assert f"{ACTION_ENGAGEMENT_ROLLOUT}:7" in callbacks
    assert f"{ACTION_ENGAGEMENT_ROLLOUT}:14" in callbacks
    assert f"{ACTION_ENGAGEMENT_ROLLOUT}:30" in callbacks
    assert ACTION_ENGAGEMENT_ADMIN_ADVANCED in callbacks
    assert "Home" in labels


def test_parse_callback_data_handles_engagement_rollout_action() -> None:
    assert parse_callback_data("eng:admin:roll:30") == (ACTION_ENGAGEMENT_ROLLOUT, ["30"])


@pytest.mark.asyncio
async def test_engagement_rollout_callback_renders_summary_with_markup() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:admin:roll:30")

    await callback_query(update, _context(client))

    assert client.rollout_calls == [{"window_days": 30}]
    reply = update.callback_query.message.replies[0]
    assert "Semantic rollout | 30 days" in reply["text"]
    assert f"{ACTION_ENGAGEMENT_ROLLOUT}:14" in _callbacks(reply["reply_markup"])
