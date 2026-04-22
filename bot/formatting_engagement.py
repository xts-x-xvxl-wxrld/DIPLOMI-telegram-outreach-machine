from __future__ import annotations

from typing import Any

from .formatting_common import (
    _action_block,
    _bullet,
    _engagement_target_readiness,
    _engagement_target_next_actions,
    _target_permission_summary,
    _engagement_settings_readiness,
    _target_status_label,
    _settings_mode_label,
    _field,
    _headline,
    _section,
    _shorten,
    _status_icon,
    _yes_no,
    _format_time_value,
    _percent,
)
from .formatting_engagement_review import (
    format_engagement_action_card,
    format_engagement_actions,
    format_engagement_candidate_card,
    format_engagement_candidate_review,
    format_engagement_candidate_revisions,
    format_engagement_candidates,
    format_engagement_semantic_rollout,
)

def format_engagement_home(data: dict[str, Any]) -> str:
    counts = data.get("counts") or data
    pending_count = counts.get("pending_reply_count", counts.get("needs_review", 0))
    approved_count = counts.get("approved_reply_count", counts.get("approved", 0))
    failed_count = counts.get("failed_candidate_count", counts.get("failed", 0))
    active_topic_count = counts.get("active_topic_count", counts.get("active_topics", 0))
    return "\n".join(
        [
            _headline("Engagement today", icon="💬"),
            _field("Review replies", pending_count, icon="⚠"),
            _field("Approved to send", approved_count, icon="✅"),
            _field("Needs attention", failed_count, icon="⛔"),
            _field("Active topics", active_topic_count, icon="🧩"),
            *_action_block(
                [
                    "Today: /engagement",
                    "Review replies: /engagement_candidates needs_review",
                    "Approved to send: /engagement_candidates approved",
                    "Communities: /engagement_targets",
                    "Settings lookup: /engagement_settings <community_id>",
                    "Topics: /engagement_topics",
                    "Recent actions: /engagement_actions",
                    "Admin: /engagement_admin",
                ]
            ),
        ]
    )


def format_engagement_admin_home(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            _headline("Engagement admin", icon="🛠"),
            _field("Communities", data.get("target_count", 0)),
            _field("Topics", data.get("topic_count", data.get("active_topic_count", 0))),
            _field("Prompt profiles", data.get("prompt_profile_count", 0)),
            _field("Voice rules", data.get("style_rule_count", 0)),
            *_action_block(
                [
                    "Communities: /engagement_targets",
                    "Topics: /engagement_topics",
                    "Voice rules: /engagement_style",
                    "Limits and accounts: /engagement_settings <community_id>",
                    "Advanced prompts: /engagement_prompts",
                ]
            ),
        ]
    )


def format_engagement_admin_limits_home() -> str:
    return "\n".join(
        [
            _headline("Limits and accounts", icon="⚙"),
            _bullet(
                "Open a community first, then tune its posting limits, quiet hours, and engagement account.",
                icon="➡",
            ),
            *_action_block(
                [
                    "Settings lookup: /engagement_settings <community_id>",
                    "Masked account lookup: /accounts",
                    "Communities: /engagement_targets",
                ]
            ),
        ]
    )


def format_engagement_settings_lookup(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "\n".join(
            [
                _headline("Settings lookup", icon="⚙"),
                _bullet("No approved engagement communities are ready for settings lookup.", icon="📭"),
                "",
                _section("Open directly", icon="➡"),
                "/engagement_settings <community_id>",
            ]
        )
    return "\n".join(
        [
            _headline(f"Settings lookup ({offset + 1}-{offset + len(items)} of {total})", icon="⚙"),
            _bullet(
                "Open a community below to review readiness, posting limits, quiet hours, and account assignment.",
                icon="➡",
            ),
            "",
            _field("Direct command", "/engagement_settings <community_id>"),
        ]
    )


def format_engagement_admin_advanced_home() -> str:
    return "\n".join(
        [
            _headline("Advanced engagement", icon="🧪"),
            _bullet("Use these controls when you need prompt profiles, diagnostics, or audit detail.", icon="➡"),
            *_action_block(
                [
                    "Prompt profiles: /engagement_prompts",
                    "Semantic rollout: /engagement_rollout",
                    "Audit and diagnostics: /engagement_actions",
                ]
            ),
        ]
    )


def format_engagement_targets(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    status = data.get("status")
    status_label = f" | {status}" if status else ""
    if not items:
        return "\n".join(
            [
                _headline(f"No engagement targets{status_label} in this view.", icon="📭"),
                "",
                _bullet(
                    "Add one with /add_engagement_target <telegram_link_or_username_or_community_id>",
                    icon="➡",
                ),
            ]
        )
    return "\n".join(
        [
            _headline(
                f"Engagement targets{status_label} ({offset + 1}-{offset + len(items)} of {total})",
                icon="🏘",
            ),
            _bullet("Add: /add_engagement_target <telegram_link_or_username_or_community_id>", icon="➡"),
        ]
    )


def format_engagement_target_card(
    item: dict[str, Any],
    *,
    index: int | None = None,
    detail: bool = False,
) -> str:
    target_id = item.get("id", "unknown")
    label = item.get("community_title") or item.get("submitted_ref") or "Target"
    heading = f"{index}. {label}" if index is not None else str(label)
    readiness = _engagement_target_readiness(item)
    lines = [
        _headline(heading, icon="🏘"),
        _field("Readiness", readiness, icon=_status_icon(readiness)),
        _field("Status", _target_status_label(item), icon=_status_icon(item.get("status"))),
        _field(
            "Allowed",
            (
                f"watch/draft {_yes_no(item.get('allow_detect'))}, "
                f"join {_yes_no(item.get('allow_join'))}, "
                f"post reviewed replies {_yes_no(item.get('allow_post'))}"
            ),
        ),
    ]
    if item.get("submitted_ref"):
        lines.append(_field("Submitted", item["submitted_ref"], icon="🔗"))
    if item.get("community_id"):
        lines.append(_field("Settings", f"/engagement_settings {item['community_id']}", icon="⚙"))
    if item.get("community_id"):
        lines.append(_field("Community", item.get("community_title") or item["community_id"]))
    if item.get("notes"):
        lines.append(_field("Notes", _shorten(str(item["notes"]), 240), icon="📝"))
    if item.get("last_error"):
        lines.append(_field("Error", _shorten(str(item["last_error"]), 240), icon="⛔"))
    if detail:
        lines.extend(
            [
                "",
                _section("Audit fields", icon="🆔"),
                _field("Target ID", target_id),
                _field("Community ID", item.get("community_id") or "unresolved"),
                _field("Raw status", item.get("status", "unknown")),
                _field(
                    "Raw permissions",
                    (
                        f"allow_join={_yes_no(item.get('allow_join'))}, "
                        f"allow_detect={_yes_no(item.get('allow_detect'))}, "
                        f"allow_post={_yes_no(item.get('allow_post'))}"
                    ),
                ),
            ]
        )
    lines.extend(
        _action_block(
            _engagement_target_next_actions(target_id, str(item.get("status") or "unknown"))
        )
    )
    return "\n".join(lines)


def format_engagement_target_mutation(
    *,
    action: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> str:
    return "\n".join(
        [
            _headline(f"Engagement target {action}.", icon="✅"),
            _field("Before", _target_permission_summary(before)),
            _field("After", _target_permission_summary(after)),
            "",
            format_engagement_target_card(after, detail=True),
        ]
    )


def format_engagement_target_approval_confirmation(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
) -> str:
    return "\n".join(
        [
            _headline("Confirm target approval", icon="⚠"),
            _field("Target ID", before.get("id", "unknown")),
            _field("Community", before.get("community_title") or before.get("community_id") or "unresolved"),
            _field("Before", _target_permission_summary(before)),
            _field("After", _target_permission_summary(after)),
            "",
            _bullet(
                "Approval enables watching, joining, and reviewed public posting for this engagement target.",
                icon="➡",
            ),
        ]
    )


def format_engagement_target_permission_confirmation(
    *,
    permission: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> str:
    return "\n".join(
        [
            _headline(f"Confirm target {permission} permission change", icon="⚠"),
            _field("Target ID", before.get("id", "unknown")),
            _field("Community", before.get("community_title") or before.get("community_id") or "unresolved"),
            _field("Before", _target_permission_summary(before)),
            _field("After", _target_permission_summary(after)),
            "",
            _bullet(
                "Posting remains public-reply only and still requires candidate approval before send.",
                icon="➡",
            ),
        ]
    )


def format_engagement_collection_runs(
    data: dict[str, Any],
    *,
    target_id: str,
) -> str:
    items = data.get("items") or []
    if not items:
        return "\n".join(
            [
                _headline("No collection runs for this engagement target yet.", icon=""),
                _field("Target ID", target_id),
                _bullet(f"Start one with /target_collect {target_id}", icon="->"),
            ]
        )

    lines = [
        _headline(f"Collection runs | latest {len(items)}", icon=""),
        _field("Target ID", target_id),
    ]
    for index, item in enumerate(items[:10], start=1):
        run_id = item.get("id", "unknown")
        lines.extend(
            [
                "",
                f"{index}. {item.get('status', 'unknown')}",
                _field("Collection run ID", run_id),
                _field("Messages seen", item.get("messages_seen", 0)),
                _field("Members seen", item.get("members_seen", 0)),
                _field("Started", item.get("started_at", "unknown")),
                _field("Completed", item.get("completed_at") or "not completed"),
            ]
        )
        if item.get("status") == "completed":
            lines.append(_bullet(f"Detect latest activity: /target_detect {target_id}", icon="->"))
    return "\n".join(lines)


def format_engagement_prompt_profiles(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return _headline("No engagement prompt profiles configured yet.", icon="📭")
    return _headline(
        f"Engagement prompt profiles ({offset + 1}-{offset + len(items)} of {total})",
        icon="🧠",
    )


def format_engagement_prompt_profile_card(
    item: dict[str, Any],
    *,
    index: int | None = None,
    detail: bool = False,
) -> str:
    profile_id = item.get("id", "unknown")
    name = item.get("name") or "Prompt profile"
    heading = f"{index}. {name}" if index is not None else str(name)
    active = "active" if item.get("active") else "inactive"
    lines = [
        _headline(heading, icon="🧠"),
        _field("State", f"{active} | version {item.get('current_version_number') or 'none'}"),
        _field(
            "Model",
            (
                f"{item.get('model', 'unknown')} | temp {item.get('temperature', 0.2)} | "
                f"max {item.get('max_output_tokens', 1000)}"
            ),
        ),
    ]
    if item.get("description"):
        lines.append(_field("Description", _shorten(str(item["description"]), 180)))
    if detail:
        lines.extend(
            [
                "",
                _section("Audit fields", icon="🆔"),
                _field("Profile ID", profile_id),
                _field("Output schema", item.get("output_schema_name", "engagement_detection_v1")),
            ]
        )
        if item.get("current_version_id"):
            lines.append(_field("Current version ID", item["current_version_id"]))
        if item.get("system_prompt"):
            lines.append(_field("System", _shorten(str(item["system_prompt"]), 400)))
        if item.get("user_prompt_template"):
            lines.append(_field("User template", _shorten(str(item["user_prompt_template"]), 500)))
    lines.extend(
        _action_block(
            [
                f"Open: /engagement_prompt {profile_id}",
                f"Versions: /engagement_prompt_versions {profile_id}",
                f"Edit: /edit_engagement_prompt {profile_id} <field>",
                f"Duplicate: /duplicate_engagement_prompt {profile_id} <new name>",
                f"Preview: /engagement_prompt_preview {profile_id}",
            ]
        )
    )
    return "\n".join(lines)


def format_engagement_prompt_versions(data: dict[str, Any], *, profile_id: str) -> str:
    items = data.get("items") or []
    if not items:
        return _headline(f"No prompt profile versions found for {profile_id}.", icon="📭")
    lines = [
        _headline(f"Prompt profile versions ({len(items)})", icon="🧠"),
        _field("Profile ID", profile_id, icon="🆔"),
    ]
    for item in items[:10]:
        lines.extend(
            [
                "",
                _headline(f"Version {item.get('version_number', 'unknown')}", icon="•"),
                _field("Version ID", item.get("id", "unknown")),
                _field(
                    "Model",
                    (
                        f"{item.get('model', 'unknown')} | temp {item.get('temperature', 0.2)} | "
                        f"max {item.get('max_output_tokens', 1000)}"
                    ),
                ),
                _field("Schema", item.get("output_schema_name", "engagement_detection_v1")),
                _field("Created by", item.get("created_by", "unknown")),
                _field("System", _shorten(str(item.get("system_prompt") or ""), 240)),
                _field("User template", _shorten(str(item.get("user_prompt_template") or ""), 280)),
                _bullet(
                    f"Rollback: /rollback_engagement_prompt {profile_id} {item.get('version_number', 'unknown')}",
                    icon="➡",
                ),
            ]
        )
    return "\n".join(lines)


def format_engagement_prompt_activation_confirmation(item: dict[str, Any]) -> str:
    return "\n".join(
        [
            _headline("Confirm prompt activation", icon="⚠"),
            _field("Profile ID", item.get("id", "unknown")),
            _field("Name", item.get("name", "Prompt profile")),
            _field("Version", item.get("current_version_number") or "none"),
            _field("Model", item.get("model", "unknown")),
            _field("Temperature", item.get("temperature", 0.2)),
            _field("Max output tokens", item.get("max_output_tokens", 1000)),
            _field("Output schema", item.get("output_schema_name", "engagement_detection_v1")),
            "",
            _bullet("Activation changes which prompt profile future engagement detection uses.", icon="➡"),
        ]
    )


def format_engagement_prompt_rollback_confirmation(
    profile: dict[str, Any],
    version: dict[str, Any],
) -> str:
    return "\n".join(
        [
            _headline("Confirm prompt rollback", icon="⚠"),
            _field("Profile ID", profile.get("id", "unknown")),
            _field("Name", profile.get("name", "Prompt profile")),
            _field("Rollback to version", version.get("version_number", "unknown")),
            _field("Version ID", version.get("id", "unknown")),
            _field("Model", version.get("model", "unknown")),
            _field("Temperature", version.get("temperature", 0.2)),
            _field("Max output tokens", version.get("max_output_tokens", 1000)),
            _field("Output schema", version.get("output_schema_name", "engagement_detection_v1")),
            "",
            _bullet("Rollback creates a new immutable version from this older version.", icon="➡"),
        ]
    )


def format_engagement_prompt_preview(data: dict[str, Any]) -> str:
    lines = [
        _headline(f"Prompt preview | {data.get('profile_name', 'profile')}", icon="🔍"),
        _field("Model", data.get("model", "unknown")),
        "",
        _section("System prompt", icon="🧠"),
        _shorten(str(data.get("system_prompt") or ""), 900),
        "",
        _section("Rendered user prompt", icon="📝"),
        _shorten(str(data.get("rendered_user_prompt") or ""), 2400),
    ]
    return "\n".join(lines)


def format_engagement_style_rules(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return _headline("No engagement style rules in this view.", icon="📭")
    scope_type = data.get("scope_type")
    scope_id = data.get("scope_id")
    scope_label = "all scopes"
    if scope_type:
        scope_label = str(scope_type)
        if scope_id:
            scope_label = f"{scope_label} {scope_id}"
    return _headline(
        f"Engagement style rules ({offset + 1}-{offset + len(items)} of {total}) | {scope_label}",
        icon="🗣",
    )


def format_engagement_style_rule_card(
    item: dict[str, Any],
    *,
    index: int | None = None,
    detail: bool = False,
) -> str:
    rule_id = item.get("id", "unknown")
    heading = (
        f"{index}. {item.get('name') or 'Style rule'}"
        if index is not None
        else str(item.get("name") or "Style rule")
    )
    scope = str(item.get("scope_type", "global"))
    scope_id = item.get("scope_id")
    scope_line = f"Scope: {scope}"
    if scope_id:
        scope_line = f"{scope_line} {scope_id}"
    lines = [
        _headline(heading, icon="🗣"),
        _field("Scope", scope_line.removeprefix("Scope: ")),
        _field(
            "Status",
            f"{'active' if item.get('active') else 'inactive'} | priority {item.get('priority', 100)}",
            icon=_status_icon("active" if item.get("active") else "inactive"),
        ),
        _field("Rule", _shorten(str(item.get("rule_text") or ""), 500)),
    ]
    if detail:
        lines.extend(
            [
                "",
                _section("Audit fields", icon="🆔"),
                _field("Rule ID", rule_id),
                _field("Scope ID", scope_id or "-"),
            ]
        )
    lines.extend(
        _action_block(
            [
                f"Open: /engagement_style_rule {rule_id}",
                f"Edit: /edit_style_rule {rule_id}",
                f"Toggle: /toggle_style_rule {rule_id} {'off' if item.get('active') else 'on'}",
            ]
        )
    )
    return "\n".join(lines)


def format_engagement_settings(
    data: dict[str, Any],
    *,
    assigned_account_label: str | None = None,
) -> str:
    community_id = data.get("community_id", "unknown")
    title = data.get("community_title") or data.get("title") or data.get("community_name")
    readiness = _engagement_settings_readiness(data)
    lines = [
        _headline(f"Engagement settings | {title}" if title else "Engagement settings", icon="⚙"),
        _field("Readiness", readiness, icon=_status_icon(readiness)),
        _field("Posting posture", _settings_mode_label(data.get("mode"))),
        _field("Joining allowed", _yes_no(data.get("allow_join"))),
        _field("Reviewed public replies allowed", _yes_no(data.get("allow_post"))),
        _field(
            "Safety floor",
            f"reply-only {_yes_no(data.get('reply_only'))}, approval required {_yes_no(data.get('require_approval'))}",
        ),
        _field(
            "Pacing",
            (
                f"{data.get('max_posts_per_day', 1)} per day, "
                f"{data.get('min_minutes_between_posts', 240)} minutes apart"
            ),
        ),
    ]
    if data.get("quiet_hours_start") or data.get("quiet_hours_end"):
        lines.append(
            _field(
                "Quiet hours",
                (
                    f"{_format_time_value(data.get('quiet_hours_start'))}-"
                    f"{_format_time_value(data.get('quiet_hours_end'))}"
                ),
            )
        )
    if data.get("assigned_account_id"):
        lines.append(
            _field("Engagement account", assigned_account_label or data["assigned_account_id"])
        )
    else:
        lines.append(_field("Engagement account", "not assigned"))
    lines.extend(
        [
            "",
            _section("Audit fields", icon="🆔"),
            _field("Community ID", community_id),
            _field("Raw mode", data.get("mode", "disabled")),
        ]
    )
    lines.extend(
        _action_block(
            [
                f"Preset: /set_engagement {community_id} <off|observe|suggest|ready>",
                (
                    "Limits: /set_engagement_limits "
                    f"{community_id} <max_posts_per_day> <min_minutes_between_posts>"
                ),
                (
                    "Quiet hours: /set_engagement_quiet_hours "
                    f"{community_id} <HH:MM> <HH:MM>"
                ),
                f"Clear quiet hours: /clear_engagement_quiet_hours {community_id}",
                (
                    "Assign account: /assign_engagement_account "
                    f"{community_id} <telegram_account_id>"
                ),
                f"Clear account: /clear_engagement_account {community_id}",
                f"Join: /join_community {community_id}",
                f"Detect: /detect_engagement {community_id}",
            ]
        )
    )
    return "\n".join(lines)


def format_engagement_account_assignment_confirmation(
    data: dict[str, Any],
    *,
    after_account_label: str,
    before_account_label: str,
) -> str:
    return "\n".join(
        [
            _headline("Confirm engagement account assignment", icon="⚠"),
            _field("Community ID", data.get("community_id", "unknown")),
            _field("Before", before_account_label),
            _field("After", after_account_label),
            "",
            _bullet(
                "The API will validate that the account belongs to the engagement pool before saving.",
                icon="➡",
            ),
        ]
    )


def format_engagement_topics(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return _headline("No engagement topics configured yet.", icon="📭")
    active_count = sum(1 for item in items if item.get("active"))
    return _headline(
        f"Engagement topics ({offset + 1}-{offset + len(items)} of {total}) | active {active_count}",
        icon="🧩",
    )


def format_engagement_topic_card(
    item: dict[str, Any],
    *,
    index: int | None = None,
    detail: bool = False,
) -> str:
    topic_id = item.get("id", "unknown")
    name = item.get("name") or "Untitled topic"
    heading = f"{index}. {name}" if index is not None else str(name)
    keywords = item.get("trigger_keywords") or []
    negative_keywords = item.get("negative_keywords") or []
    good_examples = item.get("example_good_replies") or []
    bad_examples = item.get("example_bad_replies") or []
    lines = [
        _headline(heading, icon="🧩"),
        _field(
            "Status",
            "active" if item.get("active") else "inactive",
            icon=_status_icon("active" if item.get("active") else "inactive"),
        ),
    ]
    if detail:
        lines.append(_field("Topic ID", topic_id, icon="🆔"))
    if item.get("description"):
        lines.append(_field("Description", _shorten(str(item["description"]), 160)))
    if keywords:
        lines.append(_field("Notice", _shorten(", ".join(str(value) for value in keywords), 160)))
    if negative_keywords:
        lines.append(_field("Avoid", _shorten(", ".join(str(value) for value in negative_keywords), 160)))
    lines.append(_field("Guidance", _shorten(str(item.get("stance_guidance") or ""), 260)))
    if good_examples:
        lines.append(
            "Good examples: "
            + " | ".join(
                f"#{index + 1} {_shorten(str(example), 100)}"
                for index, example in enumerate(good_examples[:2])
            )
        )
    if bad_examples:
        lines.append(
            "Bad examples (avoid copying): "
            + " | ".join(
                f"#{index + 1} {_shorten(str(example), 100)}"
                for index, example in enumerate(bad_examples[:2])
            )
        )
    lines.extend(
        _action_block(
            [
                f"Open: /engagement_topic {topic_id}",
                f"Edit guidance: /edit_topic_guidance {topic_id}",
                f"Edit triggers: /topic_keywords {topic_id} trigger <comma_keywords>",
                f"Edit negatives: /topic_keywords {topic_id} negative <comma_keywords>",
                f"Toggle: /toggle_engagement_topic {topic_id} {'off' if item.get('active') else 'on'}",
            ]
        )
    )
    if good_examples:
        lines.append(f"Remove good example: /topic_remove_example {topic_id} good <index>")
    if bad_examples:
        lines.append(f"Remove bad example: /topic_remove_example {topic_id} bad <index>")
    return "\n".join(lines)


def format_engagement_job_response(
    data: dict[str, Any],
    *,
    label: str,
    community_id: str | None = None,
    candidate_id: str | None = None,
) -> str:
    job = data.get("job") or {}
    job_id = job.get("id", "unknown")
    lines = [
        _headline(f"{label} queued.", icon="⏳"),
        _field("Job", f"{job_id} ({job.get('type', 'unknown')})"),
        _field("Status", job.get("status", "queued"), icon=_status_icon(job.get("status"))),
        _bullet(f"Check it with /job {job_id}", icon="➡"),
    ]
    if community_id:
        lines.append(_field("Community", f"/community {community_id}", icon="🏘"))
    if candidate_id:
        lines.append(_field("Candidate ID", candidate_id, icon="🆔"))
    return "\n".join(lines)
