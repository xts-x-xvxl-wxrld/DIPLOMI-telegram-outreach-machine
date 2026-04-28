from __future__ import annotations


from .formatting_common import _headline, _field, _shorten


def format_engagement_list(payload: dict) -> str:
    items = payload.get("items") or []
    total = int(payload.get("total", len(items)))
    offset = int(payload.get("offset", 0))
    if not items:
        return "No engagements"
    end = offset + len(items)
    return f"My engagements ({offset + 1}-{end} of {total})"


def format_engagement_row(engagement: dict) -> str:
    primary_label = engagement.get("primary_label") or "Engagement"
    community_label = engagement.get("community_label") or ""
    sending_mode_label = engagement.get("sending_mode_label") or ""
    issue_count = int(engagement.get("issue_count") or 0)

    badges: list[str] = []
    if sending_mode_label:
        badges.append(f"[{sending_mode_label}]")
    if issue_count > 0:
        issue_label = "1 issue" if issue_count == 1 else f"{issue_count} issues"
        badges.append(f"[{issue_label}]")

    badge_suffix = " " + " ".join(badges) if badges else ""
    lines = [f"{primary_label}{badge_suffix}"]
    if community_label:
        lines.append(community_label)
    return "\n".join(lines)


def format_engagement_detail(payload: dict) -> str:
    target_label = payload.get("target_label") or "-"
    topic_label = payload.get("topic_label") or "-"
    account_label = payload.get("account_label") or "-"
    sending_mode_label = payload.get("sending_mode_label") or "-"
    approval_count = int(payload.get("approval_count") or 0)
    issue_count = int(payload.get("issue_count") or 0)

    lines = [
        _headline("Engagement detail", icon="💬"),
        _field("Target", target_label),
        _field("Topic", topic_label),
        _field("Account", account_label),
        _field("Sending mode", sending_mode_label),
        _field("Approvals", approval_count),
        _field("Issues", issue_count),
    ]

    pending_task = payload.get("pending_task")
    if pending_task:
        task_label = pending_task.get("label") or pending_task.get("task_kind") or "Pending task"
        task_count = int(pending_task.get("count") or 0)
        count_suffix = f" ({task_count})" if task_count > 0 else ""
        lines.append(_field("Pending task", f"{task_label}{count_suffix}", icon="⚠"))

    return "\n".join(lines)


def format_sent_messages(payload: dict) -> str:
    items = payload.get("items") or []
    total = int(payload.get("total", len(items)))
    offset = int(payload.get("offset", 0))
    if not items:
        return "No sent messages"
    end = offset + len(items)
    return f"Sent messages ({offset + 1}-{end} of {total})"


def format_sent_message_row(msg: dict) -> str:
    message_text = _shorten(str(msg.get("message_text") or ""), 160)
    community_label = msg.get("community_label") or ""
    sent_at = msg.get("sent_at") or ""
    lines = [message_text]
    if community_label:
        lines.append(community_label)
    if sent_at:
        lines.append(str(sent_at))
    return "\n".join(lines)
