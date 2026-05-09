from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.engagement_approval_notifications import (
    APPROVAL_DRAFT_NOTIFIER_TASK_KEY,
    approval_draft_already_notified,
    mark_approval_draft_notified,
    send_new_approval_draft_notifications,
    start_approval_draft_notifier,
    stop_approval_draft_notifier,
)


class _FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    async def send_message(self, *, chat_id: int, text: str, reply_markup: Any | None = None) -> None:
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )


class _FakeApiClient:
    def __init__(self) -> None:
        self.calls: list[int] = []
        self.pages: dict[int, dict[str, Any]] = {
            0: {
                "queue_count": 2,
                "updating_count": 0,
                "offset": 0,
                "empty_state": "none",
                "placeholders": [],
                "current": {
                    "draft_id": "draft-1",
                    "engagement_id": "eng-1",
                    "target_label": "Founder Circle",
                    "engagement_label": "CRM migration evaluation",
                    "community_label": "@founder_circle",
                    "source_excerpt": "We are comparing CRM ownership and integrations.",
                    "text": "Compare ownership and integrations first.",
                    "why": "Relevant CRM discussion.",
                    "badge": None,
                },
            },
            1: {
                "queue_count": 2,
                "updating_count": 0,
                "offset": 1,
                "empty_state": "none",
                "placeholders": [],
                "current": {
                    "draft_id": "draft-2",
                    "engagement_id": "eng-2",
                    "target_label": "Dev Circle",
                    "engagement_label": "Developer outreach",
                    "community_label": "@dev_circle",
                    "source_excerpt": "How are people handling outbound personalization at scale?",
                    "text": "Keep the rollout narrower and more specific.",
                    "why": "Follow up on the target's last thread.",
                    "badge": None,
                },
            },
        }

    async def get_engagement_cockpit_approvals(self, *, offset: int = 0, draft_id: str | None = None) -> dict[str, Any]:
        del draft_id
        self.calls.append(offset)
        return dict(self.pages[offset])


def _application(*, operator_ids: tuple[int, ...] = (42,)) -> Any:
    return SimpleNamespace(
        bot=_FakeBot(),
        bot_data={
            "api_client": _FakeApiClient(),
            "settings": SimpleNamespace(
                admin_user_ids=frozenset(operator_ids),
                allowed_user_ids=frozenset(),
            ),
        },
    )


@pytest.mark.asyncio
async def test_send_new_approval_draft_notifications_sends_unseen_drafts() -> None:
    application = _application()

    await send_new_approval_draft_notifications(application)

    sent_messages = application.bot.sent_messages
    assert len(sent_messages) == 2
    assert sent_messages[0]["chat_id"] == 42
    assert "New draft ready for review" in sent_messages[0]["text"]
    assert "Founder Circle" in sent_messages[0]["text"]
    assert "Dev Circle" in sent_messages[1]["text"]
    assert application.bot_data["api_client"].calls == [0, 1]


@pytest.mark.asyncio
async def test_send_new_approval_draft_notifications_dedupes_per_operator() -> None:
    application = _application()
    mark_approval_draft_notified(application, operator_id=42, draft_id="draft-1")

    await send_new_approval_draft_notifications(application)

    sent_messages = application.bot.sent_messages
    assert len(sent_messages) == 1
    assert "Dev Circle" in sent_messages[0]["text"]
    assert approval_draft_already_notified(application, operator_id=42, draft_id="draft-1") is True
    assert approval_draft_already_notified(application, operator_id=42, draft_id="draft-2") is True


@pytest.mark.asyncio
async def test_start_and_stop_approval_draft_notifier_manage_task() -> None:
    application = _application(operator_ids=(42,))
    application.bot_data["approval_draft_notify_poll_interval_seconds"] = 60

    start_approval_draft_notifier(application)
    task = application.bot_data.get(APPROVAL_DRAFT_NOTIFIER_TASK_KEY)
    assert task is not None

    await stop_approval_draft_notifier(application)

    assert application.bot_data.get(APPROVAL_DRAFT_NOTIFIER_TASK_KEY) is None


@pytest.mark.asyncio
async def test_start_approval_draft_notifier_skips_without_explicit_operator_ids() -> None:
    application = _application(operator_ids=())

    start_approval_draft_notifier(application)

    assert application.bot_data.get(APPROVAL_DRAFT_NOTIFIER_TASK_KEY) is None
