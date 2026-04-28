from __future__ import annotations

from typing import Any

from .formatting_common import (
    _bullet,
    _field,
    _headline,
    _shorten,
    _status_icon,
)

_ISSUE_ICONS: dict[str, str] = {
    "topics_not_chosen": "🧩",
    "account_not_connected": "📲",
    "sending_is_paused": "⏸",
    "reply_expired": "⏰",
    "reply_failed": "⛔",
    "target_not_approved": "🔐",
    "target_not_resolved": "🔍",
    "community_permissions_missing": "🔒",
    "rate_limit_active": "🚦",
    "quiet_hours_active": "🌙",
    "account_restricted": "🚫",
}

_ISSUE_TIPS: dict[str, str] = {
    "topics_not_chosen": "Choose or create a topic to enable detection for this engagement.",
    "account_not_connected": "Assign and join an engagement account so replies can be sent.",
    "sending_is_paused": "Resume sending to allow automated reply delivery.",
    "reply_expired": "Review deadlines more promptly or adjust detection frequency.",
    "reply_failed": "Retry or investigate the send failure.",
    "target_not_approved": "Approve the community target to unlock detection and sending.",
    "target_not_resolved": "Resolve the target so a community can be identified.",
    "community_permissions_missing": "Fix permission settings to match the current sending mode.",
    "rate_limit_active": "Wait for the limit to clear or adjust send pacing.",
    "quiet_hours_active": "Adjust quiet-hours window or wait for it to pass.",
    "account_restricted": "Assign a different engagement account.",
}


def format_issue_queue(
    data: dict[str, Any],
    *,
    offset: int = 0,
    scoped: bool = False,
) -> str:
    queue_count = data.get("queue_count", 0)
    empty_state = data.get("empty_state") or "All clear."
    if queue_count == 0 or data.get("current") is None:
        scope_note = " for this engagement" if scoped else ""
        return "\n".join(
            [
                _headline(f"Issue queue{scope_note}", icon="⚠"),
                _bullet(empty_state, icon="✅"),
            ]
        )
    label = "Engagement issue queue" if not scoped else "Issues for this engagement"
    return "\n".join(
        [
            _headline(f"{label} — {queue_count} open", icon="⚠"),
            _bullet(f"Showing issue {offset + 1} of {queue_count}.", icon="•"),
        ]
    )


def format_issue_card(
    item: dict[str, Any],
    *,
    index: int | None = None,
    skipped: bool = False,
) -> str:
    issue_type = str(item.get("issue_type") or "unknown")
    issue_label = item.get("issue_label") or issue_type.replace("_", " ").title()
    icon = _ISSUE_ICONS.get(issue_type, "⚠")
    engagement_id = str(item.get("engagement_id") or "")
    target_label = item.get("target_label") or "Unknown engagement"
    context_text = item.get("context")
    tip = _ISSUE_TIPS.get(issue_type)

    heading = f"{index}. {issue_label}" if index is not None else issue_label
    if skipped:
        heading = f"{heading} (skipped before)"

    lines = [
        _headline(heading, icon=icon),
        _field("Engagement", _shorten(target_label, 200)),
    ]
    if context_text:
        lines.append(_field("Context", _shorten(context_text, 240)))
    if tip:
        lines.append(_bullet(tip, icon="➡"))
    if item.get("candidate_id"):
        lines.append(_field("Candidate", str(item["candidate_id"]), icon="💬"))
    if item.get("community_id"):
        lines.append(_field("Community", str(item["community_id"]), icon="🏘"))
    if item.get("issue_id"):
        lines.append(_field("Issue ID", str(item["issue_id"]), icon="🆔"))
    if engagement_id:
        lines.append(_field("Engagement ID", engagement_id, icon="🆔"))
    return "\n".join(lines)


def format_rate_limit_detail(data: dict[str, Any]) -> str:
    title = data.get("title") or "Rate limit active"
    target_label = data.get("target_label") or ""
    blocked_action_label = data.get("blocked_action_label") or "Send reply"
    scope_label = data.get("scope_label") or "Send limit"
    reset_at = data.get("reset_at")
    message = data.get("message") or "Sending is paused until the limit clears."

    lines = [
        _headline(title, icon="🚦"),
    ]
    if target_label:
        lines.append(_field("Engagement", _shorten(target_label, 200)))
    lines.extend(
        [
            _field("Blocked action", blocked_action_label),
            _field("Limit scope", scope_label),
            _field("Reason", _shorten(message, 300)),
        ]
    )
    if reset_at:
        lines.append(_field("Estimated reset", str(reset_at)[:19].replace("T", " ") + " UTC"))
    else:
        lines.append(_field("Reset", "Unknown — check account status"))
    lines.extend(
        [
            "",
            _bullet("No action needed — sending resumes automatically once the limit clears.", icon="➡"),
        ]
    )
    return "\n".join(lines)


def format_quiet_hours_state(data: dict[str, Any]) -> str:
    title = data.get("title") or "Quiet hours"
    target_label = data.get("target_label") or ""
    enabled = data.get("quiet_hours_enabled")
    start = data.get("quiet_hours_start")
    end = data.get("quiet_hours_end")

    lines = [
        _headline(title, icon="🌙"),
    ]
    if target_label:
        lines.append(_field("Engagement", _shorten(target_label, 200)))
    if enabled is None:
        lines.append(_field("Status", "Unknown"))
    elif enabled:
        lines.append(_field("Status", "Enabled", icon=_status_icon("active")))
        start_str = _format_time_field(start) if start else "not set"
        end_str = _format_time_field(end) if end else "not set"
        lines.append(_field("Window", f"{start_str} – {end_str}"))
    else:
        lines.append(_field("Status", "Disabled", icon="•"))
    lines.extend(
        [
            "",
            _bullet("Send HH:MM-HH:MM to set quiet hours, or 'off' to disable them.", icon="➡"),
            _bullet("Example: 22:00-08:00", icon="•"),
        ]
    )
    return "\n".join(lines)


def format_quiet_hours_saved(data: dict[str, Any]) -> str:
    enabled = data.get("quiet_hours_enabled")
    start = data.get("quiet_hours_start")
    end = data.get("quiet_hours_end")
    lines = [_headline("Quiet hours updated.", icon="✅")]
    if enabled:
        start_str = _format_time_field(start) if start else "not set"
        end_str = _format_time_field(end) if end else "not set"
        lines.append(_field("Window", f"{start_str} – {end_str}"))
    else:
        lines.append(_bullet("Quiet hours disabled.", icon="•"))
    return "\n".join(lines)


def format_issue_action_result(status: str, *, message: str | None = None) -> str:
    if status == "resolved":
        return _headline("Issue resolved.", icon="✅")
    if status == "noop":
        return _headline("No change needed.", icon="•")
    if status == "stale":
        return _headline("Issue resolved or changed — refreshing queue.", icon="✅")
    if status == "blocked":
        return "\n".join(
            [
                _headline("Action blocked.", icon="⛔"),
                _bullet(message or "This action cannot be performed right now.", icon="➡"),
            ]
        )
    return _headline(f"Action result: {status}", icon="•")


def _format_time_field(value: Any) -> str:
    if value is None:
        return "not set"
    text = str(value)
    # Handle time objects as HH:MM
    if ":" in text:
        parts = text.split(":")
        if len(parts) >= 2:
            return f"{parts[0]}:{parts[1]}"
    return text


__all__ = [
    "format_issue_queue",
    "format_issue_card",
    "format_rate_limit_detail",
    "format_quiet_hours_state",
    "format_quiet_hours_saved",
    "format_issue_action_result",
]
