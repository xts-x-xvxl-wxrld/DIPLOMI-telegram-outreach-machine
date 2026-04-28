from __future__ import annotations

from typing import Any

from .ui_common import (
    ACTION_OP_APPROVE,
    ACTION_OP_ISSUES,
    ACTION_OP_ENGS,
    ACTION_OP_SENT,
    ACTION_OP_ADD,
    ACTION_ENGAGEMENT_APPROVAL_QUEUE,
    ACTION_ENGAGEMENT_ISSUE_QUEUE,
    _button,
    _inline_markup,
)


def cockpit_home_markup(payload: dict[str, Any]):
    """Build the Engagements home markup from the cockpit home payload.

    Button visibility rules per spec:
    - first_run: only [Add engagement]
    - approvals: Approve draft, Top issues (if any), My engagements, Add engagement
                 (Sent messages hidden in this state)
    - issues: Top issues, Add engagement, My engagements, Sent messages (if has_sent)
    - clear: Add engagement, My engagements, Top issues (if any), Sent messages (if has_sent)

    No back or home navigation on this screen.
    """
    state = payload.get("state", "first_run")
    draft_count = payload.get("draft_count", 0) or 0
    issue_count = payload.get("issue_count", 0) or 0
    has_sent_messages = bool(payload.get("has_sent_messages"))

    rows = []

    if state == "first_run":
        rows.append([_button("Add engagement", ACTION_OP_ADD)])
        return _inline_markup(rows)

    if state == "approvals":
        approve_label = (
            f"Approve draft ({draft_count})" if draft_count > 0 else "Approve draft"
        )
        rows.append([_button(approve_label, ACTION_ENGAGEMENT_APPROVAL_QUEUE, "list", "0")])
        if issue_count > 0:
            issues_label = f"Top issues ({issue_count})"
            rows.append([_button(issues_label, ACTION_ENGAGEMENT_ISSUE_QUEUE, "list", "0")])
        rows.append([_button("My engagements", ACTION_OP_ENGS)])
        rows.append([_button("Add engagement", ACTION_OP_ADD)])
        # Sent messages hidden in approval-focused state
        return _inline_markup(rows)

    if state == "issues":
        issues_label = (
            f"Top issues ({issue_count})" if issue_count > 0 else "Top issues"
        )
        rows.append([_button(issues_label, ACTION_ENGAGEMENT_ISSUE_QUEUE, "list", "0")])
        rows.append([_button("Add engagement", ACTION_OP_ADD)])
        rows.append([_button("My engagements", ACTION_OP_ENGS)])
        if has_sent_messages:
            rows.append([_button("Sent messages", ACTION_OP_SENT)])
        return _inline_markup(rows)

    # state == "clear"
    rows.append([_button("Add engagement", ACTION_OP_ADD)])
    rows.append([_button("My engagements", ACTION_OP_ENGS)])
    if issue_count > 0:
        issues_label = f"Top issues ({issue_count})"
        rows.append([_button(issues_label, ACTION_ENGAGEMENT_ISSUE_QUEUE, "list", "0")])
    if has_sent_messages:
        rows.append([_button("Sent messages", ACTION_OP_SENT)])
    return _inline_markup(rows)


__all__ = ["cockpit_home_markup"]
