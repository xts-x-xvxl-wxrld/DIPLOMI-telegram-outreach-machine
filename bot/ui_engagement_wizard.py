from __future__ import annotations

from typing import Sequence

from .ui_common import (
    ACTION_ENGAGEMENT_HOME,
    ACTION_ENGAGEMENT_WIZARD,
    _button,
    _compact_label,
    _inline_markup,
    _with_navigation,
    compact_uuid,
)


# ---------------------------------------------------------------------------
# Step 1: target prompt — no markup needed (user types text)
# ---------------------------------------------------------------------------


def engagement_wizard_step1_markup():
    """Cancel button only for Step 1 (target entry)."""
    rows: list[list[object]] = []
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


# ---------------------------------------------------------------------------
# Step 2: topic picker (single-select)
# ---------------------------------------------------------------------------


def engagement_wizard_topics_markup(
    topics: Sequence[dict[str, object]],
    *,
    selected_id: str | None = None,
    engagement_id: str,
    has_selection: bool = False,
):
    rows = []
    for topic in topics:
        topic_id = str(topic.get("id") or "")
        if not topic_id:
            continue
        name = str(topic.get("name") or topic_id)
        checked = "✓ " if topic_id == selected_id else "☐ "
        rows.append(
            [_button(f"{checked}{_compact_label(name, 30)}", ACTION_ENGAGEMENT_WIZARD, "tp", compact_uuid(topic_id), compact_uuid(engagement_id))]
        )
    rows.append([_button("➕ Create topic", ACTION_ENGAGEMENT_WIZARD, "tpnew", compact_uuid(engagement_id))])
    if has_selection:
        rows.append([_button("Continue →", ACTION_ENGAGEMENT_WIZARD, "step", "3", engagement_id)])
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


# ---------------------------------------------------------------------------
# Step 3: account picker
# ---------------------------------------------------------------------------


def engagement_wizard_accounts_markup(
    accounts: Sequence[dict[str, object]],
    *,
    engagement_id: str,
):
    rows = []
    for account in accounts:
        acct_id = str(account.get("id") or "")
        if not acct_id:
            continue
        phone = str(account.get("phone") or acct_id)
        rows.append([_button(f"📲 {phone}", ACTION_ENGAGEMENT_WIZARD, "ap", compact_uuid(acct_id), compact_uuid(engagement_id))])
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


# ---------------------------------------------------------------------------
# Step 4: mode picker
# ---------------------------------------------------------------------------


def engagement_wizard_level_markup(engagement_id: str):
    rows = [
        [
            _button("👀 Watching", ACTION_ENGAGEMENT_WIZARD, "lv", "watching", engagement_id),
            _button("✍ Suggesting", ACTION_ENGAGEMENT_WIZARD, "lv", "suggesting", engagement_id),
            _button("📤 Sending", ACTION_ENGAGEMENT_WIZARD, "lv", "sending", engagement_id),
        ],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


# ---------------------------------------------------------------------------
# Step 5: review + confirm
# ---------------------------------------------------------------------------


def engagement_wizard_launch_markup(engagement_id: str):
    rows = [
        [_button("🚀 Confirm", ACTION_ENGAGEMENT_WIZARD, "confirm", engagement_id)],
        [
            _button("✏ Topic", ACTION_ENGAGEMENT_WIZARD, "edit", engagement_id, "topic"),
            _button("✏ Account", ACTION_ENGAGEMENT_WIZARD, "edit", engagement_id, "account"),
            _button("✏ Mode", ACTION_ENGAGEMENT_WIZARD, "edit", engagement_id, "mode"),
        ],
        [_button("✖ Cancel", ACTION_ENGAGEMENT_WIZARD, "cancel", engagement_id)],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


# ---------------------------------------------------------------------------
# Retry markup (shown after validation/stale failure)
# ---------------------------------------------------------------------------


def engagement_wizard_retry_markup(engagement_id: str):
    rows = [
        [_button("🔁 Retry", ACTION_ENGAGEMENT_WIZARD, "retry", engagement_id)],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


# ---------------------------------------------------------------------------
# Cancel confirmation markup
# ---------------------------------------------------------------------------


def engagement_wizard_cancel_confirm_markup(engagement_id: str):
    rows = [
        [
            _button("Yes, cancel", ACTION_ENGAGEMENT_WIZARD, "cancel_yes", engagement_id),
            _button("No, continue", ACTION_ENGAGEMENT_WIZARD, "step", "5", engagement_id),
        ],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))
