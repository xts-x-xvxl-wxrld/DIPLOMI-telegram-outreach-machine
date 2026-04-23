from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.main import (
    API_CLIENT_KEY,
    ACCOUNT_ONBOARDING_STORE_KEY,
    add_account_command,
    callback_query,
    help_command,
    seeds_command,
    accounts_command,
    start_command,
    telegram_entity_text,
)
from bot.ui import (
    ACTION_DISC_ACTIVITY,
    ACTION_DISC_ALL,
    ACTION_DISC_ATTENTION,
    ACTION_DISC_HELP,
    ACTION_DISC_HOME,
    ACTION_DISC_REVIEW,
    ACTION_DISC_START,
    ACTION_DISC_WATCHING,
    ACTION_ENGAGEMENT_HOME,
    ACTION_OP_ACCOUNTS,
    ACTION_OP_ADD_ACCOUNT,
    ACTION_OP_DISCOVERY,
    ACTION_OP_HELP,
    ACTION_OP_HOME,
)


class _FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.replies: list[dict[str, Any]] = []
        self.deleted = False

    async def reply_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.replies.append({"text": text, "reply_markup": reply_markup})

    async def delete(self) -> None:
        self.deleted = True


class _FakeCallbackQuery:
    def __init__(self, data: str, *, user_id: int = 123) -> None:
        self.data = data
        self.message = _FakeMessage()
        self.from_user = SimpleNamespace(id=user_id, username="operator")
        self.answers: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append({"text": text, "show_alert": show_alert})

    async def edit_message_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.edits.append({"text": text, "reply_markup": reply_markup})


class _FakeApiClient:
    def __init__(self) -> None:
        self.accounts_calls = 0
        self.seed_group_calls = 0
        self.candidate_list_calls: list[dict[str, Any]] = []
        self.topic_calls = 0
        self.started_onboarding: list[dict[str, Any]] = []
        self.completed_onboarding: list[dict[str, Any]] = []

        self.accounts_data = {
            "counts": {"available": 2, "in_use": 0, "rate_limited": 0, "banned": 0},
            "counts_by_pool": {"search": 1, "engagement": 1, "disabled": 0},
            "items": [
                {"phone": "+***1234", "account_pool": "search", "status": "available"},
                {"phone": "+***5678", "account_pool": "engagement", "status": "available"},
            ],
        }
        self.seed_groups_data = {
            "items": [
                {
                    "id": "sg-1",
                    "name": "Hungarian SaaS founders",
                    "seed_count": 5,
                    "unresolved_count": 0,
                    "resolved_count": 5,
                    "failed_count": 0,
                }
            ],
            "total": 1,
        }
        self.candidates_data = {
            "needs_review": {"items": [], "total": 0},
            "approved": {"items": [], "total": 0},
            "failed": {"items": [], "total": 0},
        }
        self.topics_data = {"items": [], "total": 0}

    async def get_accounts(self) -> dict[str, Any]:
        self.accounts_calls += 1
        return self.accounts_data

    async def start_account_onboarding(self, **payload: Any) -> dict[str, Any]:
        self.started_onboarding.append(payload)
        return {
            "status": "code_sent",
            "account_pool": payload["account_pool"],
            "phone": payload["phone"],
            "session_file_name": payload["session_name"] or "account.session",
            "phone_code_hash": "hash-1",
        }

    async def complete_account_onboarding(self, **payload: Any) -> dict[str, Any]:
        self.completed_onboarding.append(payload)
        return {
            "status": "registered",
            "account_pool": payload["account_pool"],
            "phone": payload["phone"],
            "session_file_name": payload["session_name"],
        }

    async def list_seed_groups(self) -> dict[str, Any]:
        self.seed_group_calls += 1
        return self.seed_groups_data

    async def list_engagement_candidates(
        self, *, status: str = "needs_review", limit: int = 1, offset: int = 0, **_: Any
    ) -> dict[str, Any]:
        self.candidate_list_calls.append({"status": status, "limit": limit, "offset": offset})
        return self.candidates_data.get(status, {"items": [], "total": 0})

    async def list_engagement_topics(self) -> dict[str, Any]:
        self.topic_calls += 1
        return self.topics_data


def _make_update(message_text: str | None = None) -> Any:
    message = _FakeMessage(text=message_text)
    return SimpleNamespace(
        message=message,
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


def _make_context(client: _FakeApiClient | None = None) -> Any:
    app_data: dict[str, Any] = {}
    if client is not None:
        app_data[API_CLIENT_KEY] = client
    return SimpleNamespace(
        args=[],
        application=SimpleNamespace(bot_data=app_data),
    )


# ---------------------------------------------------------------------------
# /start handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_command_sends_keyboard_remove_then_cockpit() -> None:
    update = _make_update("/start")
    context = _make_context()

    await start_command(update, context)

    replies = update.message.replies
    assert len(replies) == 2
    # First reply clears the old keyboard
    assert "cockpit" in replies[0]["text"].lower()
    first_markup = replies[0]["reply_markup"]
    assert first_markup is not None
    # ReplyKeyboardRemove — not an inline markup (has no inline_keyboard attribute)
    assert not hasattr(first_markup, "inline_keyboard")
    # Second reply is the operator cockpit with inline buttons
    second_markup = replies[1]["reply_markup"]
    assert hasattr(second_markup, "inline_keyboard")
    cockpit_callbacks = [
        button.callback_data
        for row in second_markup.inline_keyboard
        for button in row
    ]
    assert ACTION_OP_DISCOVERY in cockpit_callbacks
    assert ACTION_OP_ACCOUNTS in cockpit_callbacks
    assert ACTION_OP_HELP in cockpit_callbacks


@pytest.mark.asyncio
async def test_start_command_does_not_attach_reply_keyboard() -> None:
    update = _make_update("/start")
    context = _make_context()

    await start_command(update, context)

    for reply in update.message.replies:
        markup = reply["reply_markup"]
        if markup is not None:
            # Reply keyboard markup has a `keyboard` attribute (list of rows of buttons)
            assert not hasattr(markup, "keyboard"), (
                "start_command must not attach a persistent reply keyboard"
            )


# ---------------------------------------------------------------------------
# /help handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_help_command_renders_help_with_cockpit_navigation() -> None:
    update = _make_update("/help")
    context = _make_context()

    await help_command(update, context)

    replies = update.message.replies
    assert len(replies) == 1
    markup = replies[0]["reply_markup"]
    assert hasattr(markup, "inline_keyboard")
    cockpit_callbacks = [
        button.callback_data for row in markup.inline_keyboard for button in row
    ]
    assert ACTION_OP_DISCOVERY in cockpit_callbacks
    assert ACTION_OP_ACCOUNTS in cockpit_callbacks
    # Help text contains expected keywords
    assert "/seeds" in replies[0]["text"] or "commands" in replies[0]["text"].lower()


# ---------------------------------------------------------------------------
# /accounts handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accounts_command_renders_masked_account_health() -> None:
    client = _FakeApiClient()
    update = _make_update("/accounts")
    context = _make_context(client)

    await accounts_command(update, context)

    assert client.accounts_calls == 1
    replies = update.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "account" in text.lower()
    # Phone numbers are masked by the API — no raw digits in the pool section
    assert "+***1234" in text or "masked" in text or "available" in text
    callbacks = [
        button.callback_data
        for row in replies[0]["reply_markup"].inline_keyboard
        for button in row
    ]
    assert f"{ACTION_OP_ADD_ACCOUNT}:search" in callbacks
    assert f"{ACTION_OP_ADD_ACCOUNT}:engagement" in callbacks


@pytest.mark.asyncio
async def test_add_account_command_starts_search_onboarding_and_deletes_command() -> None:
    client = _FakeApiClient()
    update = _make_update("/add_account")
    context = _make_context(client)
    context.args = ["search", "+10000000000", "research-1", "warm", "spare"]

    await add_account_command(update, context)

    assert update.message.deleted is True
    assert client.started_onboarding == [
        {
            "account_pool": "search",
            "phone": "+10000000000",
            "session_name": "research-1.session",
            "notes": "warm spare",
            "requested_by": "telegram:123:@operator",
        }
    ]
    replies = update.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "Telegram login code sent" in text
    assert "+10000000000" not in text
    assert "research-1.session" in text
    assert context.application.bot_data[ACCOUNT_ONBOARDING_STORE_KEY][123]["step"] == "code"


@pytest.mark.asyncio
async def test_account_onboarding_text_completes_login_and_deletes_code() -> None:
    client = _FakeApiClient()
    context = _make_context(client)
    context.application.bot_data[ACCOUNT_ONBOARDING_STORE_KEY] = {
        123: {
            "step": "code",
            "account_pool": "engagement",
            "phone": "+10000000001",
            "session_file_name": "engagement-1.session",
            "phone_code_hash": "hash-1",
            "notes": "public replies",
        }
    }
    update = _make_update("12345")

    await telegram_entity_text(update, context)

    assert update.message.deleted is True
    assert client.completed_onboarding == [
        {
            "account_pool": "engagement",
            "phone": "+10000000001",
            "session_name": "engagement-1.session",
            "phone_code_hash": "hash-1",
            "code": "12345",
            "password": None,
            "notes": "public replies",
            "requested_by": "telegram:123:@operator",
        }
    ]
    assert context.application.bot_data[ACCOUNT_ONBOARDING_STORE_KEY] == {}
    assert "Telegram account added" in update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_add_account_command_rejects_invalid_pool() -> None:
    update = _make_update("/add_account")
    context = _make_context()
    context.args = ["disabled", "+10000000000"]

    await add_account_command(update, context)

    text = update.message.replies[0]["text"]
    assert "Usage: /add_account" in text
    assert "account_pool must be search or engagement" in text


# ---------------------------------------------------------------------------
# /seeds handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seeds_command_lists_searches() -> None:
    client = _FakeApiClient()
    update = _make_update("/seeds")
    context = _make_context(client)

    await seeds_command(update, context)

    assert client.seed_group_calls == 1
    all_text = " ".join(r["text"] for r in update.message.replies)
    assert "Hungarian SaaS founders" in all_text


# ---------------------------------------------------------------------------
# op:home callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_op_home_callback_renders_operator_cockpit() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_OP_HOME)
    context = _make_context(client)

    await callback_query(update, context)

    replies = update.callback_query.message.replies
    assert any("cockpit" in r["text"].lower() for r in replies)
    markups = [r["reply_markup"] for r in replies if r["reply_markup"] is not None]
    assert markups
    cockpit_callbacks = [
        button.callback_data
        for markup in markups
        for row in markup.inline_keyboard
        for button in row
    ]
    assert ACTION_OP_DISCOVERY in cockpit_callbacks


# ---------------------------------------------------------------------------
# op:discovery callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_op_discovery_callback_opens_discovery_cockpit() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_OP_DISCOVERY)
    context = _make_context(client)

    await callback_query(update, context)

    replies = update.callback_query.message.replies
    assert any("discovery" in r["text"].lower() for r in replies)
    markups = [r["reply_markup"] for r in replies if r["reply_markup"] is not None]
    assert markups
    disc_callbacks = [
        button.callback_data
        for markup in markups
        for row in markup.inline_keyboard
        for button in row
    ]
    assert ACTION_DISC_START in disc_callbacks
    assert ACTION_DISC_ATTENTION in disc_callbacks
    assert ACTION_DISC_REVIEW in disc_callbacks
    assert ACTION_DISC_WATCHING in disc_callbacks
    assert ACTION_DISC_ACTIVITY in disc_callbacks


# ---------------------------------------------------------------------------
# disc:home callback (same as op:discovery)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disc_home_callback_opens_discovery_cockpit() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_DISC_HOME)
    context = _make_context(client)

    await callback_query(update, context)

    replies = update.callback_query.message.replies
    assert any("discovery" in r["text"].lower() for r in replies)


# ---------------------------------------------------------------------------
# Discovery cockpit destinations route to seed helpers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disc_all_callback_lists_seed_groups() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_DISC_ALL)
    context = _make_context(client)

    await callback_query(update, context)

    assert client.seed_group_calls == 1
    all_text = " ".join(r["text"] for r in update.callback_query.message.replies)
    assert "Hungarian SaaS founders" in all_text


@pytest.mark.asyncio
async def test_disc_attention_callback_uses_seed_groups_helper() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_DISC_ATTENTION)
    context = _make_context(client)

    await callback_query(update, context)

    assert client.seed_group_calls == 1


@pytest.mark.asyncio
async def test_disc_review_callback_uses_seed_groups_helper() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_DISC_REVIEW)
    context = _make_context(client)

    await callback_query(update, context)

    assert client.seed_group_calls == 1


@pytest.mark.asyncio
async def test_disc_watching_callback_uses_seed_groups_helper() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_DISC_WATCHING)
    context = _make_context(client)

    await callback_query(update, context)

    assert client.seed_group_calls == 1


@pytest.mark.asyncio
async def test_disc_start_callback_shows_guidance() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_DISC_START)
    context = _make_context(client)

    await callback_query(update, context)

    replies = update.callback_query.message.replies
    assert replies
    combined = " ".join(r["text"] for r in replies).lower()
    assert "csv" in combined or "upload" in combined or "@username" in combined


@pytest.mark.asyncio
async def test_disc_activity_callback_shows_guidance() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_DISC_ACTIVITY)
    context = _make_context(client)

    await callback_query(update, context)

    replies = update.callback_query.message.replies
    assert replies
    combined = " ".join(r["text"] for r in replies).lower()
    assert "job" in combined


@pytest.mark.asyncio
async def test_disc_help_callback_shows_discovery_help() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_DISC_HELP)
    context = _make_context(client)

    await callback_query(update, context)

    replies = update.callback_query.message.replies
    assert replies
    combined = " ".join(r["text"] for r in replies).lower()
    assert "group_name" in combined or "csv" in combined


# ---------------------------------------------------------------------------
# op:accounts callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_op_accounts_callback_renders_account_health_with_masking() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_OP_ACCOUNTS)
    context = _make_context(client)

    await callback_query(update, context)

    assert client.accounts_calls == 1
    all_text = " ".join(r["text"] for r in update.callback_query.message.replies)
    assert "account" in all_text.lower()
    # Markup should contain account-specific add actions and cockpit navigation
    markups = [r["reply_markup"] for r in update.callback_query.message.replies if r["reply_markup"]]
    assert markups
    callbacks = [
        button.callback_data
        for markup in markups
        for row in markup.inline_keyboard
        for button in row
    ]
    assert f"{ACTION_OP_ADD_ACCOUNT}:search" in callbacks
    assert f"{ACTION_OP_ADD_ACCOUNT}:engagement" in callbacks
    assert ACTION_OP_HOME in callbacks


@pytest.mark.asyncio
async def test_add_account_callback_renders_pool_specific_usage() -> None:
    update = _make_callback_update(f"{ACTION_OP_ADD_ACCOUNT}:engagement")
    context = _make_context(_FakeApiClient())

    await callback_query(update, context)

    replies = update.callback_query.message.replies
    assert replies
    text = replies[0]["text"]
    assert "Usage: /add_account engagement <phone>" in text
    callbacks = [
        button.callback_data
        for row in replies[0]["reply_markup"].inline_keyboard
        for button in row
    ]
    assert ACTION_OP_ACCOUNTS in callbacks


# ---------------------------------------------------------------------------
# op:help callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_op_help_callback_renders_help_with_cockpit_navigation() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_OP_HELP)
    context = _make_context(client)

    await callback_query(update, context)

    replies = update.callback_query.message.replies
    assert replies
    markups = [r["reply_markup"] for r in replies if r["reply_markup"]]
    assert markups
    nav_callbacks = [
        button.callback_data
        for markup in markups
        for row in markup.inline_keyboard
        for button in row
    ]
    assert ACTION_OP_DISCOVERY in nav_callbacks or ACTION_OP_HOME in nav_callbacks


# ---------------------------------------------------------------------------
# Regression: existing engagement cockpit callbacks still route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engagement_home_callback_still_routes() -> None:
    client = _FakeApiClient()
    update = _make_callback_update(ACTION_ENGAGEMENT_HOME)
    context = _make_context(client)

    await callback_query(update, context)

    # The engagement home handler was invoked (it queries candidates and topics)
    assert client.topic_calls == 1
    replies = update.callback_query.message.replies
    assert replies
    assert any("engagement" in r["text"].lower() for r in replies)
