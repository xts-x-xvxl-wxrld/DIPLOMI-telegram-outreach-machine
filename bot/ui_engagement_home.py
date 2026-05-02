from __future__ import annotations

from typing import Any

from .ui_common import (
    ACTION_OP_APPROVE,
    ACTION_OP_ISSUES,
    ACTION_OP_ENGS,
    ACTION_OP_SENT,
    ACTION_OP_ADD,
    _button,
    _inline_markup,
)


def _label_with_count(label: str, count: int) -> str:
    return f"{label} ({count})" if count > 0 else label


def cockpit_home_markup(payload: dict[str, Any]):
    """Build the Engagements home markup from the cockpit home payload.

    Home keeps every destination visible so hidden slash commands do not remove
    access to empty-state screens. State changes button order, not destination
    visibility.

    No back or home navigation on this screen.
    """
    state = payload.get("state", "first_run")
    draft_count = payload.get("draft_count", 0) or 0
    issue_count = payload.get("issue_count", 0) or 0
    approve_row = [
        _button(_label_with_count("Approve draft", draft_count), ACTION_OP_APPROVE)
    ]
    issues_row = [
        _button(_label_with_count("Top issues", issue_count), ACTION_OP_ISSUES)
    ]
    my_engagements_row = [_button("My engagements", ACTION_OP_ENGS)]
    add_engagement_row = [_button("Add engagement", ACTION_OP_ADD)]
    sent_messages_row = [_button("Sent messages", ACTION_OP_SENT)]

    if state == "first_run":
        return _inline_markup(
            [
                add_engagement_row,
                my_engagements_row,
                issues_row,
                approve_row,
                sent_messages_row,
            ]
        )

    if state == "approvals":
        return _inline_markup(
            [
                approve_row,
                issues_row,
                my_engagements_row,
                add_engagement_row,
                sent_messages_row,
            ]
        )

    if state == "issues":
        return _inline_markup(
            [
                issues_row,
                add_engagement_row,
                my_engagements_row,
                approve_row,
                sent_messages_row,
            ]
        )

    return _inline_markup(
        [
            add_engagement_row,
            my_engagements_row,
            issues_row,
            approve_row,
            sent_messages_row,
        ]
    )


__all__ = ["cockpit_home_markup"]
