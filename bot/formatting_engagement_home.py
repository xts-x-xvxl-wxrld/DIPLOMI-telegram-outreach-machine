from __future__ import annotations

from typing import Any


def format_cockpit_home(payload: dict[str, Any]) -> str:
    state = payload.get("state", "first_run")
    draft_count = payload.get("draft_count", 0) or 0
    issue_count = payload.get("issue_count", 0) or 0
    active_engagement_count = payload.get("active_engagement_count", 0) or 0

    lines = ["Engagements", ""]

    if state == "first_run":
        lines.append("No engagements yet.")
        lines.append("Tap Add engagement to start tracking one community.")
        return "\n".join(lines)

    if state == "approvals":
        draft_word = "draft" if draft_count == 1 else "drafts"
        lines.append(f"Needs review: {draft_count} {draft_word}.")
        if issue_count > 0:
            issue_word = "issue" if issue_count == 1 else "issues"
            latest = payload.get("latest_issue_preview")
            if latest and latest.get("issue_label"):
                lines.append(f"Also open: {issue_count} {issue_word}. Latest: {latest['issue_label']}.")
            else:
                lines.append(f"Also open: {issue_count} {issue_word}.")
        return "\n".join(lines)

    if state == "issues":
        issue_word = "issue" if issue_count == 1 else "issues"
        lines.append(f"Needs attention: {issue_count} {issue_word}.")
        lines.append("Open Top issues to clear blockers.")
        return "\n".join(lines)

    lines.append("Nothing urgent right now.")
    if active_engagement_count > 0:
        eng_word = "engagement" if active_engagement_count == 1 else "engagements"
        lines.append(f"Running: {active_engagement_count} active {eng_word}.")
    else:
        lines.append("Add an engagement whenever you're ready.")
    return "\n".join(lines)


__all__ = ["format_cockpit_home"]
