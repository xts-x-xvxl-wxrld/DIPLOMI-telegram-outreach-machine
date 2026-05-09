from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import bot.app as bot_app
from bot.app import STARTUP_BOT_COMMANDS, post_init, post_shutdown
from bot.app import API_CLIENT_KEY, CONFIG_EDIT_STORE_KEY


class _FakeBot:
    def __init__(self) -> None:
        self.commands: Any = None

    async def set_my_commands(self, commands: Any) -> bool:
        self.commands = commands
        return True


@pytest.mark.asyncio
async def test_post_init_registers_cockpit_command_menu() -> None:
    bot = _FakeBot()
    settings = SimpleNamespace(
        api_base_url="http://api.local",
        api_token="token",
        request_timeout_seconds=1.0,
        admin_user_ids=frozenset(),
        allowed_user_ids=frozenset(),
    )
    application = SimpleNamespace(bot=bot, bot_data={"settings": settings})

    await post_init(application)

    assert application.bot_data[API_CLIENT_KEY] is not None
    assert application.bot_data[CONFIG_EDIT_STORE_KEY] is not None
    assert tuple((command.command, command.description) for command in bot.commands) == STARTUP_BOT_COMMANDS
    assert STARTUP_BOT_COMMANDS == (
        ("start", "Open the main cockpit"),
        ("seeds", "Open seed groups"),
        ("engagement", "Open engagement cockpit"),
        ("accounts", "Open account cockpit"),
        ("help", "Open help"),
    )


@pytest.mark.asyncio
async def test_post_init_starts_approval_notifier() -> None:
    bot = _FakeBot()
    settings = SimpleNamespace(
        api_base_url="http://api.local",
        api_token="token",
        request_timeout_seconds=1.0,
        admin_user_ids=frozenset({42}),
        allowed_user_ids=frozenset(),
    )
    application = SimpleNamespace(bot=bot, bot_data={"settings": settings})
    started: list[Any] = []

    original_start = bot_app.start_approval_draft_notifier
    bot_app.start_approval_draft_notifier = lambda app: started.append(app)
    try:
        await post_init(application)
    finally:
        bot_app.start_approval_draft_notifier = original_start
        client = application.bot_data.get(API_CLIENT_KEY)
        if client is not None:
            await client.aclose()

    assert started == [application]


@pytest.mark.asyncio
async def test_post_shutdown_stops_approval_notifier() -> None:
    application = SimpleNamespace(bot_data={API_CLIENT_KEY: SimpleNamespace(aclose=_fake_aclose)})
    stopped: list[Any] = []

    async def fake_stop(app: Any) -> None:
        stopped.append(app)

    original_stop = bot_app.stop_approval_draft_notifier
    bot_app.stop_approval_draft_notifier = fake_stop
    try:
        await post_shutdown(application)
    finally:
        bot_app.stop_approval_draft_notifier = original_stop

    assert stopped == [application]


async def _fake_aclose() -> None:
    return None
