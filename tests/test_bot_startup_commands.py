from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.app import STARTUP_BOT_COMMANDS, post_init
from bot.app import API_CLIENT_KEY, CONFIG_EDIT_STORE_KEY


class _FakeBot:
    def __init__(self) -> None:
        self.commands: Any = None

    async def set_my_commands(self, commands: Any) -> bool:
        self.commands = commands
        return True


@pytest.mark.asyncio
async def test_post_init_publishes_start_command_for_empty_conversations() -> None:
    bot = _FakeBot()
    settings = SimpleNamespace(
        api_base_url="http://api.local",
        api_token="token",
        request_timeout_seconds=1.0,
    )
    application = SimpleNamespace(bot=bot, bot_data={"settings": settings})

    await post_init(application)

    assert application.bot_data[API_CLIENT_KEY] is not None
    assert application.bot_data[CONFIG_EDIT_STORE_KEY] is not None
    assert bot.commands == STARTUP_BOT_COMMANDS
    assert STARTUP_BOT_COMMANDS[0][0] == "start"
    assert any(command == "start" for command, _ in STARTUP_BOT_COMMANDS)
