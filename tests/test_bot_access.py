from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.config import BotSettings
from bot.main import (
    API_CLIENT_KEY,
    _is_authorized_update,
    _is_engagement_admin,
    _is_engagement_admin_async,
    _is_identity_command,
    _message_command_name,
)


def _settings(
    *allowed_user_ids: int,
    admin_user_ids: tuple[int, ...] = (),
) -> BotSettings:
    return BotSettings(
        telegram_bot_token="telegram-token",
        api_base_url="http://api.test/api",
        api_token="api-token",
        allowed_user_ids=frozenset(allowed_user_ids),
        admin_user_ids=frozenset(admin_user_ids),
    )


def test_empty_allowed_user_list_keeps_bot_open() -> None:
    update = SimpleNamespace(effective_user=SimpleNamespace(id=123))

    assert _is_authorized_update(update, _settings())


def test_allowed_user_list_permits_known_researcher() -> None:
    update = SimpleNamespace(effective_user=SimpleNamespace(id=456))

    assert _is_authorized_update(update, _settings(123, 456))


def test_allowed_user_list_blocks_unknown_researcher() -> None:
    update = SimpleNamespace(effective_user=SimpleNamespace(id=789))

    assert not _is_authorized_update(update, _settings(123, 456))


def test_whoami_command_bypasses_access_gate_for_onboarding() -> None:
    update = SimpleNamespace(message=SimpleNamespace(text="/whoami@discovery_bot"))

    assert _message_command_name(update) == "whoami"
    assert _is_identity_command(update)


def test_engagement_admin_defaults_open_when_no_admin_allowlist_is_configured() -> None:
    update = SimpleNamespace(effective_user=SimpleNamespace(id=456))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"settings": _settings(123, 456)}))

    assert _is_engagement_admin(update, context)


def test_engagement_admin_requires_admin_allowlist_membership_when_configured() -> None:
    update = SimpleNamespace(effective_user=SimpleNamespace(id=456))
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={"settings": _settings(123, 456, admin_user_ids=(123,))}
        )
    )

    assert not _is_engagement_admin(update, context)


class _CapabilityClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[int | None] = []

    async def get_operator_capabilities(self, operator_user_id: int | None = None) -> dict[str, object]:
        self.calls.append(operator_user_id)
        return self.response


@pytest.mark.asyncio
async def test_backend_admin_capability_is_primary_when_available() -> None:
    update = SimpleNamespace(effective_user=SimpleNamespace(id=456))
    client = _CapabilityClient(
        {
            "operator_user_id": 456,
            "backend_capabilities_available": True,
            "engagement_admin": False,
            "source": "backend_admin_user_ids",
        }
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "settings": _settings(123, 456, admin_user_ids=(456,)),
                API_CLIENT_KEY: client,
            }
        )
    )

    assert not await _is_engagement_admin_async(update, context)
    assert not _is_engagement_admin(update, context)
    assert client.calls == [456]


@pytest.mark.asyncio
async def test_backend_capability_unconfigured_falls_back_to_local_allowlist() -> None:
    update = SimpleNamespace(effective_user=SimpleNamespace(id=456))
    client = _CapabilityClient(
        {
            "operator_user_id": 456,
            "backend_capabilities_available": False,
            "engagement_admin": None,
            "source": "unconfigured",
        }
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "settings": _settings(123, 456, admin_user_ids=(456,)),
                API_CLIENT_KEY: client,
            }
        )
    )

    assert await _is_engagement_admin_async(update, context)
    assert client.calls == [456]
