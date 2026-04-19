from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.main import (
    API_CLIENT_KEY,
    callback_query,
    engagement_candidates_command,
    engagement_command,
    send_reply_command,
    approve_reply_command,
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
        self.list_candidate_calls: list[dict[str, Any]] = []
        self.send_calls: list[dict[str, Any]] = []
        self.approve_calls: list[dict[str, Any]] = []
        self.candidates_by_status = {
            "needs_review": {
                "items": [
                    {
                        "id": "candidate-review",
                        "community_title": "Founder Circle",
                        "topic_name": "Open CRM",
                        "status": "needs_review",
                        "source_excerpt": "Discussing CRM tools.",
                        "detected_reason": "Relevant CRM discussion.",
                        "suggested_reply": "Compare ownership and integrations first.",
                    }
                ],
                "total": 1,
            },
            "approved": {
                "items": [
                    {
                        "id": "candidate-approved",
                        "community_title": "Founder Circle",
                        "topic_name": "Open CRM",
                        "status": "approved",
                        "source_excerpt": "Discussing CRM tools.",
                        "detected_reason": "Relevant CRM discussion.",
                        "suggested_reply": "Compare ownership and integrations first.",
                    }
                ],
                "total": 1,
            },
            "failed": {"items": [], "total": 3},
        }

    async def list_engagement_candidates(
        self,
        *,
        status: str = "needs_review",
        limit: int = 5,
        offset: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        self.list_candidate_calls.append({"status": status, "limit": limit, "offset": offset})
        page = self.candidates_by_status.get(status, {"items": [], "total": 0})
        return {"items": page["items"], "total": page["total"], "limit": limit, "offset": offset}

    async def list_engagement_topics(self) -> dict[str, Any]:
        return {
            "items": [
                {"id": "topic-1", "active": True},
                {"id": "topic-2", "active": False},
            ],
            "total": 2,
        }

    async def approve_engagement_candidate(
        self,
        candidate_id: str,
        *,
        reviewed_by: str,
    ) -> dict[str, Any]:
        self.approve_calls.append({"candidate_id": candidate_id, "reviewed_by": reviewed_by})
        return {
            "id": candidate_id,
            "community_title": "Founder Circle",
            "status": "approved",
            "reviewed_by": reviewed_by,
        }

    async def send_engagement_candidate(
        self,
        candidate_id: str,
        *,
        approved_by: str | None,
    ) -> dict[str, Any]:
        self.send_calls.append({"candidate_id": candidate_id, "approved_by": approved_by})
        return {"job": {"id": "send-job", "type": "engagement.send", "status": "queued"}}


def _context(client: _FakeApiClient, *args: str) -> SimpleNamespace:
    return SimpleNamespace(
        args=list(args),
        application=SimpleNamespace(bot_data={API_CLIENT_KEY: client}),
    )


def _message_update() -> SimpleNamespace:
    return SimpleNamespace(
        message=_FakeMessage(),
        callback_query=None,
        effective_user=SimpleNamespace(id=123, username="operator"),
    )


def _callback_update(data: str) -> SimpleNamespace:
    query = _FakeCallbackQuery(data)
    return SimpleNamespace(
        message=None,
        callback_query=query,
        effective_user=query.from_user,
    )


def _callback_data_values(markup: Any | None) -> list[str]:
    if markup is None:
        return []
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if getattr(button, "callback_data", None)
    ]


@pytest.mark.asyncio
async def test_engagement_command_builds_home_counts_from_api_client() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_command(update, _context(client))

    assert "Needs review: 1" in update.message.replies[0]["text"]
    assert "Approved, not sent: 1" in update.message.replies[0]["text"]
    assert "Failed candidates: 3" in update.message.replies[0]["text"]
    assert "Active topics: 1" in update.message.replies[0]["text"]
    assert [call["status"] for call in client.list_candidate_calls] == [
        "needs_review",
        "approved",
        "failed",
    ]


@pytest.mark.asyncio
async def test_engagement_candidates_approved_status_exposes_send_not_review() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_candidates_command(update, _context(client, "approved"))

    assert "Engagement replies | approved" in update.message.replies[0]["text"]
    card = update.message.replies[1]
    callbacks = _callback_data_values(card["reply_markup"])
    assert "eng:cand:send:candidate-approved" in callbacks
    assert "eng:cand:approve:candidate-approved" not in callbacks
    assert client.list_candidate_calls[0]["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_reply_returns_queue_send_button_without_sending() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await approve_reply_command(update, _context(client, "candidate-review"))

    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "Queue send: /send_reply candidate-review" in update.message.replies[0]["text"]
    assert "eng:cand:send:candidate-review" in callbacks
    assert client.approve_calls == [
        {"candidate_id": "candidate-review", "reviewed_by": "telegram:123:@operator"}
    ]
    assert client.send_calls == []


@pytest.mark.asyncio
async def test_send_reply_command_queues_send_job() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await send_reply_command(update, _context(client, "candidate-approved"))

    assert "Reply send queued." in update.message.replies[0]["text"]
    assert "send-job (engagement.send)" in update.message.replies[0]["text"]
    assert client.send_calls == [
        {"candidate_id": "candidate-approved", "approved_by": "telegram:123:@operator"}
    ]
    assert "jb:send-job" in _callback_data_values(update.message.replies[0]["reply_markup"])


@pytest.mark.asyncio
async def test_send_reply_callback_queues_send_job() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:cand:send:candidate-approved")

    await callback_query(update, _context(client))

    assert update.callback_query.answers == [{"text": None, "show_alert": False}]
    assert "Reply send queued." in update.callback_query.message.replies[0]["text"]
    assert client.send_calls == [
        {"candidate_id": "candidate-approved", "approved_by": "telegram:123:@operator"}
    ]
