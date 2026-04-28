from __future__ import annotations

from typing import Sequence

from .ui_common import (
    ACTION_ENGAGEMENT_MINE,
    ACTION_ENGAGEMENT_DETAIL,
    ACTION_ENGAGEMENT_SENT,
    ACTION_ENGAGEMENT_WIZARD,
    ACTION_OP_HOME,
    _button,
    _inline_markup,
    _with_navigation,
    _offset_pager_row,
)

_PAGE_SIZE = 20


def engagement_list_markup(
    items: Sequence[dict],
    *,
    offset: int,
    total: int,
    page_size: int = _PAGE_SIZE,
):
    rows = []
    for eng in items:
        engagement_id = str(eng.get("engagement_id") or "")
        primary_label = str(eng.get("primary_label") or "Engagement")
        sending_mode_label = str(eng.get("sending_mode_label") or "")
        issue_count = int(eng.get("issue_count") or 0)

        badge_parts: list[str] = []
        if sending_mode_label:
            badge_parts.append(sending_mode_label)
        if issue_count > 0:
            issue_label = "1 issue" if issue_count == 1 else f"{issue_count} issues"
            badge_parts.append(issue_label)

        badge_suffix = " | " + " | ".join(badge_parts) if badge_parts else ""
        label = f"{primary_label}{badge_suffix}"
        # Telegram button label limit is fairly long; compact if needed
        if len(label) > 48:
            label = label[:45].rstrip() + "..."
        rows.append([_button(label, ACTION_ENGAGEMENT_MINE, "open", engagement_id)])

    pager_row = _offset_pager_row(
        action=ACTION_ENGAGEMENT_MINE,
        offset=offset,
        total=total,
        page_size=page_size,
        prefix_parts=["list"],
    )
    if pager_row:
        # Use "Newer"/"Older" labels as per spec by replacing the defaults
        newer_older_row = []
        prev_offset = max(offset - page_size, 0)
        next_offset = offset + page_size
        if offset > 0:
            newer_older_row.append(_button("← Newer", ACTION_ENGAGEMENT_MINE, "list", str(prev_offset)))
        if next_offset < total:
            newer_older_row.append(_button("Older →", ACTION_ENGAGEMENT_MINE, "list", str(next_offset)))
        if newer_older_row:
            rows.append(newer_older_row)

    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_OP_HOME, include_home=False)
    )


def engagement_preview_markup(engagement_id: str):
    rows = [
        [_button("View details", ACTION_ENGAGEMENT_DETAIL, "open", engagement_id)],
    ]
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_ENGAGEMENT_MINE, back_parts=["list", "0"], include_home=False)
    )


def engagement_detail_markup(
    engagement_id: str,
    *,
    pending_task: dict | None = None,
):
    rows = []

    if pending_task:
        task_kind = pending_task.get("task_kind") or ""
        resume_callback = pending_task.get("resume_callback")
        if resume_callback:
            # The resume callback is a full callback string from the backend
            # We emit a button that triggers eng:det:resume:<id>
            if task_kind in ("approvals", "approval_updates"):
                label = "Approve draft"
            elif task_kind == "issues":
                label = "Top issues"
            else:
                label = "Resume task"
            rows.append([_button(label, ACTION_ENGAGEMENT_DETAIL, "resume", engagement_id)])

    rows.extend([
        [
            _button("Topic", ACTION_ENGAGEMENT_WIZARD, "edit", engagement_id, "topic"),
            _button("Account", ACTION_ENGAGEMENT_WIZARD, "edit", engagement_id, "account"),
            _button("Mode", ACTION_ENGAGEMENT_WIZARD, "edit", engagement_id, "mode"),
        ],
    ])

    return _inline_markup(
        _with_navigation(
            rows,
            back_action=ACTION_ENGAGEMENT_MINE,
            back_parts=["list", "0"],
            include_home=False,
        )
    )


def sent_messages_markup(
    *,
    offset: int,
    total: int,
    page_size: int = _PAGE_SIZE,
):
    rows = []
    prev_offset = max(offset - page_size, 0)
    next_offset = offset + page_size
    pager_row = []
    if offset > 0:
        pager_row.append(_button("← Newer", ACTION_ENGAGEMENT_SENT, "list", str(prev_offset)))
    if next_offset < total:
        pager_row.append(_button("Older →", ACTION_ENGAGEMENT_SENT, "list", str(next_offset)))
    if pager_row:
        rows.append(pager_row)

    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_OP_HOME, include_home=False)
    )
