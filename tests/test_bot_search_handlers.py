from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.main import API_CLIENT_KEY, callback_query, search_candidates_command, search_command
from bot.ui import ACTION_SEARCH_CONVERT, ACTION_SEARCH_REVIEW, ACTION_SEARCH_RUN_CANDIDATES


class _FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.replies: list[dict[str, Any]] = []

    async def reply_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.replies.append({"text": text, "reply_markup": reply_markup})


class _FakeCallbackQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = _FakeMessage()
        self.from_user = SimpleNamespace(id=123, username="operator")
        self.answers: list[dict[str, Any]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append({"text": text, "show_alert": show_alert})


class _FakeApiClient:
    def __init__(self) -> None:
        self.created_searches: list[dict[str, Any]] = []
        self.review_calls: list[dict[str, Any]] = []
        self.convert_calls: list[dict[str, Any]] = []

    async def create_search_run(self, query: str, *, requested_by: str | None = None) -> dict[str, Any]:
        self.created_searches.append({"query": query, "requested_by": requested_by})
        return {
            "search_run": {
                "id": "run-1",
                "raw_query": query,
                "normalized_title": query,
                "status": "draft",
            },
            "job": {"id": "job-1", "type": "search.plan", "status": "queued"},
        }

    async def list_search_candidates(
        self,
        search_run_id: str,
        *,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        assert search_run_id == "run-1"
        assert limit == 5
        assert offset == 0
        return {
            "items": [
                {
                    "id": "cand-1",
                    "search_run_id": "run-1",
                    "status": "promoted",
                    "community_id": "community-1",
                    "title": "Hungarian SaaS Founders",
                    "username": "husaas",
                    "telegram_url": "https://t.me/husaas",
                    "member_count": 1200,
                    "score": "72.500",
                    "score_components": {"title_username_match": 40},
                    "evidence_summary": {
                        "total": 2,
                        "types": ["entity_title_match"],
                        "snippets": ["Title matched SaaS founders"],
                    },
                }
            ],
            "total": 1,
        }

    async def review_search_candidate(
        self,
        candidate_id: str,
        *,
        action: str,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        self.review_calls.append(
            {"candidate_id": candidate_id, "action": action, "requested_by": requested_by}
        )
        return {
            "candidate": {
                "id": candidate_id,
                "search_run_id": "run-1",
                "status": "promoted",
                "community_id": "community-1",
            },
            "review": {"id": "review-1", "action": action, "scope": "run"},
        }

    async def convert_search_candidate_to_seed(
        self,
        candidate_id: str,
        *,
        seed_group_name: str | None = None,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        self.convert_calls.append(
            {
                "candidate_id": candidate_id,
                "seed_group_name": seed_group_name,
                "requested_by": requested_by,
            }
        )
        return {
            "seed_group": {"id": "sg-1", "name": "Search: Hungarian SaaS"},
            "seed_channel": {"id": "seed-1", "telegram_url": "https://t.me/husaas", "status": "resolved"},
            "candidate": {"id": candidate_id, "status": "converted_to_seed"},
            "review": {"id": "review-2", "action": "convert_to_seed", "scope": "run"},
        }


def _make_update(message_text: str | None = None) -> Any:
    return SimpleNamespace(
        message=_FakeMessage(message_text),
        callback_query=None,
        effective_user=SimpleNamespace(id=123, username="operator"),
    )


def _make_callback_update(data: str) -> Any:
    query = _FakeCallbackQuery(data)
    return SimpleNamespace(
        message=None,
        callback_query=query,
        effective_user=SimpleNamespace(id=123, username="operator"),
    )


def _make_context(client: _FakeApiClient) -> Any:
    return SimpleNamespace(
        args=[],
        application=SimpleNamespace(bot_data={API_CLIENT_KEY: client}),
    )


@pytest.mark.asyncio
async def test_search_command_creates_run_with_operator_ref() -> None:
    client = _FakeApiClient()
    update = _make_update("/search Hungarian SaaS founders")
    context = _make_context(client)
    context.args = ["Hungarian", "SaaS", "founders"]

    await search_command(update, context)

    assert client.created_searches == [
        {"query": "Hungarian SaaS founders", "requested_by": "telegram:123"}
    ]
    reply = update.message.replies[0]
    assert "Community search queued" in reply["text"]
    callbacks = [button.callback_data for row in reply["reply_markup"].inline_keyboard for button in row]
    assert any(callback.startswith(ACTION_SEARCH_RUN_CANDIDATES) for callback in callbacks)


@pytest.mark.asyncio
async def test_search_candidates_command_shows_review_and_conversion_actions() -> None:
    client = _FakeApiClient()
    update = _make_update("/search_candidates run-1")
    context = _make_context(client)
    context.args = ["run-1"]

    await search_candidates_command(update, context)

    card_reply = update.message.replies[1]
    assert "Hungarian SaaS Founders" in card_reply["text"]
    assert "Title matched SaaS founders" in card_reply["text"]
    callbacks = [button.callback_data for row in card_reply["reply_markup"].inline_keyboard for button in row]
    assert any(callback.startswith(ACTION_SEARCH_REVIEW) for callback in callbacks)
    assert any(callback.startswith(ACTION_SEARCH_CONVERT) for callback in callbacks)


@pytest.mark.asyncio
async def test_search_review_callback_promotes_candidate_then_offers_conversion() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(f"{ACTION_SEARCH_REVIEW}:cand-1:promote")
    context = _make_context(client)

    await callback_query(update, context)

    assert client.review_calls == [
        {"candidate_id": "cand-1", "action": "promote", "requested_by": "telegram:123"}
    ]
    reply = update.callback_query.message.replies[0]
    callbacks = [button.callback_data for row in reply["reply_markup"].inline_keyboard for button in row]
    assert f"{ACTION_SEARCH_CONVERT}:cand-1" in callbacks


@pytest.mark.asyncio
async def test_search_convert_callback_calls_seed_conversion_endpoint() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(f"{ACTION_SEARCH_CONVERT}:cand-1")
    context = _make_context(client)

    await callback_query(update, context)

    assert client.convert_calls == [
        {"candidate_id": "cand-1", "seed_group_name": None, "requested_by": "telegram:123"}
    ]
    assert "converted to seed" in update.callback_query.message.replies[0]["text"]
