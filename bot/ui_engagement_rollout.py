from __future__ import annotations

from .ui_common import (
    ACTION_ENGAGEMENT_ACTIONS,
    ACTION_ENGAGEMENT_ADMIN,
    ACTION_ENGAGEMENT_ADMIN_ADVANCED,
    ACTION_ENGAGEMENT_PROMPTS,
    ACTION_ENGAGEMENT_ROLLOUT,
    _button,
    _inline_markup,
    _with_navigation,
)


def engagement_admin_advanced_markup():
    rows = [
        [_button("🧠 Drafting profiles", ACTION_ENGAGEMENT_PROMPTS, "0")],
        [_button("📊 Semantic rollout", ACTION_ENGAGEMENT_ROLLOUT, "14")],
        [_button("📜 Audit/diagnostics", ACTION_ENGAGEMENT_ACTIONS, "0")],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_ADMIN))


def engagement_rollout_markup(*, window_days: int):
    rows = [[
        _button(_window_label(7, window_days), ACTION_ENGAGEMENT_ROLLOUT, "7"),
        _button(_window_label(14, window_days), ACTION_ENGAGEMENT_ROLLOUT, "14"),
        _button(_window_label(30, window_days), ACTION_ENGAGEMENT_ROLLOUT, "30"),
    ]]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_ADMIN_ADVANCED))


def _window_label(days: int, selected_days: int) -> str:
    prefix = "• " if days == selected_days else ""
    return f"{prefix}{days}d"


__all__ = ["engagement_admin_advanced_markup", "engagement_rollout_markup"]
