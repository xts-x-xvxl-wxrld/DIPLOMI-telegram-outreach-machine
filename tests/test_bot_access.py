from __future__ import annotations

from types import SimpleNamespace

from bot.config import BotSettings
from bot.main import (
    _is_authorized_update,
    _is_engagement_admin,
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
