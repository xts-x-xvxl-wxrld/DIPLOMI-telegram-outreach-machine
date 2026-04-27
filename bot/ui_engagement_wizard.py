from __future__ import annotations

from typing import Sequence

from .ui_common import (
    ACTION_ENGAGEMENT_HOME,
    ACTION_ENGAGEMENT_WIZARD,
    _button,
    _compact_label,
    _inline_markup,
    _with_navigation,
)


def engagement_wizard_topics_markup(
    topics: Sequence[dict[str, object]],
    *,
    selected_ids: Sequence[str],
    community_id: str,
    has_selection: bool = False,
):
    rows = []
    for topic in topics:
        topic_id = str(topic.get("id") or "")
        if not topic_id:
            continue
        name = str(topic.get("name") or topic_id)
        checked = "✓ " if topic_id in selected_ids else "☐ "
        rows.append([_button(f"{checked}{_compact_label(name, 30)}", ACTION_ENGAGEMENT_WIZARD, "tp", topic_id)])
    rows.append([_button("➕ Create new topic", ACTION_ENGAGEMENT_WIZARD, "tn")])
    if has_selection:
        rows.append([_button("Continue →", ACTION_ENGAGEMENT_WIZARD, "step", "3", community_id)])
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_wizard_accounts_markup(
    accounts: Sequence[dict[str, object]],
    *,
    community_id: str,
):
    rows = []
    for account in accounts:
        acct_id = str(account.get("id") or "")
        if not acct_id:
            continue
        phone = str(account.get("phone") or acct_id)
        rows.append([_button(f"📲 {phone}", ACTION_ENGAGEMENT_WIZARD, "ap", acct_id)])
    rows.append([_button("➕ Add new account", ACTION_ENGAGEMENT_WIZARD, "an", community_id)])
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_wizard_level_markup(community_id: str):
    rows = [
        [
            _button("👀 Watching", ACTION_ENGAGEMENT_WIZARD, "lv", "watching", community_id),
            _button("✍ Suggesting", ACTION_ENGAGEMENT_WIZARD, "lv", "suggesting", community_id),
            _button("📤 Sending", ACTION_ENGAGEMENT_WIZARD, "lv", "sending", community_id),
        ],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_wizard_launch_markup(community_id: str):
    rows = [[_button("🚀 Start engagement", ACTION_ENGAGEMENT_WIZARD, "go", community_id)]]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_wizard_retry_markup(community_id: str):
    rows = [[_button("🔁 Retry", ACTION_ENGAGEMENT_WIZARD, "retry", community_id)]]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))
