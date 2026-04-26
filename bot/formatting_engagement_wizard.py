from __future__ import annotations

from typing import Any

from .formatting_common import _field, _headline


def format_wizard_community_prompt() -> str:
    return "\n".join(
        [
            _headline("Add engagement community", icon="🧙"),
            "Step 1 of 5: Community",
            "",
            "Paste the @handle or t.me/... link for the community you want to engage.",
            "Example: @startups_berlin or https://t.me/startups_berlin",
            "",
            "Use /cancel_edit to stop.",
        ]
    )


def format_wizard_topics_prompt(
    topics: list[dict[str, Any]],
    *,
    community_ref: str,
    selected_ids: list[str],
) -> str:
    lines = [
        _headline(f"Community: {community_ref}", icon="🧙"),
        "Step 2 of 5: Topics",
        "",
        "Pick at least one topic the bot should watch for.",
    ]
    for topic in topics:
        topic_id = str(topic.get("id") or "")
        name = str(topic.get("name") or topic_id)
        checked = "✓" if topic_id in selected_ids else "☐"
        active_tag = "" if topic.get("active") else " (inactive)"
        lines.append(f"  {checked} {name}{active_tag}")
    if not topics:
        lines.append("No topics yet — create one with the button below.")
    lines.extend(["", "Use /cancel_edit to stop."])
    return "\n".join(lines)


def format_wizard_account_prompt(
    accounts: list[dict[str, Any]],
    *,
    community_ref: str,
) -> str:
    lines = [
        _headline(f"Community: {community_ref}", icon="🧙"),
        "Step 3 of 5: Account",
        "",
        "Which engagement account should join and engage in this community?",
    ]
    if not accounts:
        lines.extend(
            [
                "",
                "No engagement accounts available. Add one with /add_account, then restart the wizard.",
            ]
        )
    lines.extend(["", "Use /cancel_edit to stop."])
    return "\n".join(lines)


def format_wizard_level_prompt(
    *,
    community_ref: str,
    selected_topics: list[str],
) -> str:
    topic_summary = ", ".join(selected_topics) if selected_topics else "none"
    return "\n".join(
        [
            _headline(f"Community: {community_ref}", icon="🧙"),
            "Step 4 of 5: Engagement level",
            "",
            _field("Topics", topic_summary, icon="🧩"),
            "",
            "How active should this engagement be?",
            "",
            "  👀 Watching — detect matching posts, no replies",
            "  ✍ Suggesting — detect and queue replies for review",
            "  📤 Sending — detect, queue, and post approved replies",
            "",
            "Use /cancel_edit to stop.",
        ]
    )


_LEVEL_LABELS = {
    "watching": "Watching (detect only)",
    "suggesting": "Suggesting (detect + queue replies)",
    "sending": "Sending (detect + queue + post approved)",
}


def format_wizard_launch_card(
    *,
    community_ref: str,
    topic_names: list[str],
    account_phone: str,
    level: str,
) -> str:
    level_label = _LEVEL_LABELS.get(level, level)
    topic_summary = ", ".join(topic_names) if topic_names else "none"
    return "\n".join(
        [
            _headline("Ready to launch!", icon="🚀"),
            "",
            _field("Community", community_ref, icon="🏘"),
            _field("Topics", topic_summary, icon="🧩"),
            _field("Account", account_phone, icon="📲"),
            _field("Level", level_label, icon="📊"),
            "",
            "Press Start to begin engagement.",
        ]
    )
