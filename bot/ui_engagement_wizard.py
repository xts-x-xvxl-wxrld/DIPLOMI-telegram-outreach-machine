from __future__ import annotations

from typing import Sequence

from .ui_common import (
    ACTION_ENGAGEMENT_WIZARD,
    ACTION_OP_ACCOUNTS,
    ACTION_OP_ADD_ACCOUNT,
    _button,
    _compact_label,
    _inline_markup,
    compact_uuid,
)


def _wizard_navigation_row(
    *,
    engagement_id: str | None = None,
    back_step: int | None = None,
    include_cancel: bool = True,
) -> list[object]:
    row: list[object] = []
    if back_step is not None and engagement_id:
        row.append(_button("Back", ACTION_ENGAGEMENT_WIZARD, "step", str(back_step), engagement_id))
    if include_cancel:
        row.append(_button("Cancel", ACTION_ENGAGEMENT_WIZARD, "cancel", engagement_id or "new"))
    return row


def _wizard_markup(
    rows: Sequence[Sequence[object]],
    *,
    engagement_id: str | None = None,
    back_step: int | None = None,
    include_cancel: bool = True,
):
    output = [list(row) for row in rows]
    nav_row = _wizard_navigation_row(
        engagement_id=engagement_id,
        back_step=back_step,
        include_cancel=include_cancel,
    )
    if nav_row:
        output.append(nav_row)
    return _inline_markup(output)


def engagement_wizard_step1_markup():
    rows: list[list[object]] = []
    return _wizard_markup(rows, include_cancel=True)


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
    return _wizard_markup(rows, engagement_id=engagement_id, back_step=1)


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
    if not rows:
        rows.extend(
            [
                [_button("Add engagement account", ACTION_OP_ADD_ACCOUNT, "engagement")],
                [_button("Accounts", ACTION_OP_ACCOUNTS)],
            ]
        )
    return _wizard_markup(rows, engagement_id=engagement_id, back_step=2)


# ---------------------------------------------------------------------------
# Step 4: mode picker
# ---------------------------------------------------------------------------


def engagement_wizard_level_markup(engagement_id: str):
    rows = [
        [
            _button("Draft", ACTION_ENGAGEMENT_WIZARD, "lv", "draft", engagement_id),
            _button("Auto send", ACTION_ENGAGEMENT_WIZARD, "lv", "auto_send", engagement_id),
        ],
    ]
    return _wizard_markup(rows, engagement_id=engagement_id, back_step=3)


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
    return _wizard_markup(rows, engagement_id=engagement_id, back_step=4, include_cancel=False)


# ---------------------------------------------------------------------------
# Retry markup (shown after validation/stale failure)
# ---------------------------------------------------------------------------


def engagement_wizard_retry_markup(engagement_id: str):
    rows = [
        [_button("🔁 Retry", ACTION_ENGAGEMENT_WIZARD, "retry", engagement_id)],
    ]
    return _wizard_markup(rows, engagement_id=engagement_id, back_step=4)


# ---------------------------------------------------------------------------
# Cancel confirmation markup
# ---------------------------------------------------------------------------


def engagement_wizard_cancel_confirm_markup(engagement_id: str):
    rows = [
        [
            _button("Confirm cancel", ACTION_ENGAGEMENT_WIZARD, "cancel_yes", engagement_id),
            _button("Back", ACTION_ENGAGEMENT_WIZARD, "step", "5", engagement_id),
        ],
    ]
    return _inline_markup(rows)

