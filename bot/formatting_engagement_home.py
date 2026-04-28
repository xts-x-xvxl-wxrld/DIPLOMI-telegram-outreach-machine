from __future__ import annotations

from typing import Any


def format_cockpit_home(payload: dict[str, Any]) -> str:
    state = payload.get("state", "first_run")
    draft_count = payload.get("draft_count", 0) or 0
    issue_count = payload.get("issue_count", 0) or 0
    active_engagement_count = payload.get("active_engagement_count", 0) or 0

    lines = ["Engagements", ""]

    if state == "first_run":
        lines.append("Add your first engagement")
        lines.append("Tap add engagement to get started.")
        return "\n".join(lines)

    if state == "approvals":
        draft_word = "draft" if draft_count == 1 else "drafts"
        lines.append(f"{draft_count} {draft_word} need approval")
        if issue_count > 0:
            issue_word = "issue" if issue_count == 1 else "issues"
            latest = payload.get("latest_issue_preview")
            if latest and latest.get("issue_label"):
                lines.append(
                    f"{issue_count} {issue_word} need attention: {latest['issue_label']}"
                )
            else:
                lines.append(f"{issue_count} {issue_word} need attention")
        return "\n".join(lines)

    if state == "issues":
        issue_word = "issue" if issue_count == 1 else "issues"
        lines.append(f"{issue_count} {issue_word} need attention")
        return "\n".join(lines)

    # state == "clear"
    lines.append("No pending work")
    if active_engagement_count > 0:
        eng_word = "engagement" if active_engagement_count == 1 else "engagements"
        lines.append(f"{active_engagement_count} active {eng_word}")
    return "\n".join(lines)


__all__ = ["format_cockpit_home"]
