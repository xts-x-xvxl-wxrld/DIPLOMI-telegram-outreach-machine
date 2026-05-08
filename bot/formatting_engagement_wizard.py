from __future__ import annotations

from typing import Any

from .formatting_common import _field, _headline


def format_wizard_community_prompt() -> str:
    return "\n".join(
        [
            _headline("Add engagement", icon="🧭"),
            "Step 1 of 5: Community",
            "",
            "Send one Telegram handle or t.me link.",
            "Examples: @startups_berlin or https://t.me/startups_berlin",
            "",
            "Use Cancel to stop.",
        ]
    )


def format_wizard_topics_prompt(
    topics: list[dict[str, Any]],
    *,
    community_ref: str,
    selected_ids: list[str],
) -> str:
    lines = [
        _headline("Add engagement", icon="🧭"),
        "Step 2 of 5: Topics",
        "",
        _field("Community", community_ref),
        "",
        "Choose one topic to watch.",
    ]
    for topic in topics:
        topic_id = str(topic.get("id") or "")
        name = str(topic.get("name") or topic_id)
        checked = "✓" if topic_id in selected_ids else "☐"
        active_tag = "" if topic.get("active") else " (inactive)"
        lines.append(f"  {checked} {name}{active_tag}")
    if not topics:
        lines.append("No topics yet. Create one below.")
    lines.extend(["", "Use Back to change the community, or Cancel to stop."])
    return "\n".join(lines)


def format_wizard_account_prompt(
    accounts: list[dict[str, Any]],
    *,
    community_ref: str,
    account_status_note: str | None = None,
) -> str:
    lines = [
        _headline("Add engagement", icon="🧭"),
        "Step 3 of 5: Account",
        "",
        _field("Community", community_ref),
        "",
        "Choose the engagement account for this community.",
    ]
    if account_status_note:
        lines.extend(["", account_status_note])
    if not accounts:
        lines.extend(
            [
                "",
                "No engagement accounts are ready. Add one below, then come back here.",
            ]
        )
    lines.extend(["", "Use Back to change the topic, or Cancel to stop."])
    return "\n".join(lines)


def format_wizard_level_prompt(
    *,
    community_ref: str,
    selected_topics: list[str],
    account_status_note: str | None = None,
) -> str:
    topic_summary = ", ".join(selected_topics) if selected_topics else "-"
    lines = [
        _headline("Add engagement", icon="🧭"),
        "Step 4 of 5: Sending mode",
        "",
        _field("Community", community_ref),
        _field("Topics", topic_summary, icon="🧩"),
    ]
    if account_status_note:
        lines.extend(["", account_status_note])
    lines.extend(
        [
            "",
            "Choose how replies should be sent.",
            "",
            "  Draft - Review every reply before it sends",
            "  Auto send - Send automatically within limits",
            "",
            "Use Back to change the account, or Cancel to stop.",
        ]
    )
    return "\n".join(lines)


_LEVEL_LABELS = {
    "draft": "Draft",
    "auto_send": "Auto send",
}


def format_wizard_quiet_hours_prompt(
    *,
    current_quiet_hours: str,
    current_timezone: str,
) -> str:
    return "\n".join(
        [
            _headline("Add engagement", icon="🧭"),
            "Quiet hours",
            "",
            _field("Current", current_quiet_hours),
            _field("Timezone", current_timezone),
            "",
            "Choose a timezone below, then send HH:MM-HH:MM to pause sends during that window.",
            "Example: 22:00-08:00",
            "",
            "Send off or tap Turn off to clear quiet hours.",
        ]
    )


def format_wizard_launch_card(
    *,
    community_ref: str,
    topic_names: list[str],
    account_phone: str,
    level: str,
    max_posts_per_day: int,
    min_minutes_between_posts: int,
    quiet_hours_label: str,
    quiet_hours_timezone_label: str,
    account_status_note: str | None = None,
) -> str:
    level_label = _LEVEL_LABELS.get(level, level)
    topic_summary = ", ".join(topic_names) if topic_names else "-"
    lines = [
        _headline("Review engagement", icon="🚀"),
        "Step 5 of 5: Review",
        "",
        _field("Community", community_ref, icon="🏘"),
        _field("Topics", topic_summary, icon="🧩"),
        _field("Account", account_phone, icon="📲"),
        _field("Mode", level_label, icon="📊"),
        _field("Limits", f"{max_posts_per_day} per day, {min_minutes_between_posts} minute gap", icon="⏱"),
        _field("Quiet hours", quiet_hours_label, icon="🌙"),
        _field("Timezone", quiet_hours_timezone_label, icon="🕒"),
    ]
    if account_status_note:
        lines.extend(["", account_status_note])
    lines.extend(["", "Confirm starts monitoring this topic."])
    return "\n".join(lines)
