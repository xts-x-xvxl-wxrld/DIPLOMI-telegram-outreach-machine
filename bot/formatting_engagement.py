from __future__ import annotations

from typing import Any

from .formatting_common import (
    _engagement_candidate_readiness,
    _engagement_candidate_next_actions,
    _engagement_target_readiness,
    _engagement_target_next_actions,
    _target_permission_summary,
    _engagement_settings_readiness,
    _target_status_label,
    _settings_mode_label,
    _shorten,
    _yes_no,
    _format_time_value,
    _percent,
)

def format_engagement_home(data: dict[str, Any]) -> str:
    counts = data.get("counts") or data
    pending_count = counts.get("pending_reply_count", counts.get("needs_review", 0))
    approved_count = counts.get("approved_reply_count", counts.get("approved", 0))
    failed_count = counts.get("failed_candidate_count", counts.get("failed", 0))
    active_topic_count = counts.get("active_topic_count", counts.get("active_topics", 0))
    return "\n".join(
        [
            "Engagement today",
            f"Review replies: {pending_count}",
            f"Approved to send: {approved_count}",
            f"Needs attention: {failed_count}",
            f"Active topics: {active_topic_count}",
            "",
            "Today: /engagement",
            "Review replies: /engagement_candidates needs_review",
            "Approved to send: /engagement_candidates approved",
            "Communities: /engagement_targets",
            "Settings lookup: /engagement_settings <community_id>",
            "Topics: /engagement_topics",
            "Recent actions: /engagement_actions",
            "Admin: /engagement_admin",
        ]
    )


def format_engagement_admin_home(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Engagement admin",
            f"Communities: {data.get('target_count', 0)}",
            f"Topics: {data.get('topic_count', data.get('active_topic_count', 0))}",
            f"Prompt profiles: {data.get('prompt_profile_count', 0)}",
            f"Voice rules: {data.get('style_rule_count', 0)}",
            "",
            "Communities: /engagement_targets",
            "Topics: /engagement_topics",
            "Voice rules: /engagement_style",
            "Limits and accounts: /engagement_settings <community_id>",
            "Advanced prompts: /engagement_prompts",
        ]
    )


def format_engagement_admin_limits_home() -> str:
    return "\n".join(
        [
            "Limits and accounts",
            "Open a community first, then tune its posting limits, quiet hours, and engagement account.",
            "",
            "Settings lookup: /engagement_settings <community_id>",
            "Masked account lookup: /accounts",
            "Communities: /engagement_targets",
        ]
    )


def format_engagement_settings_lookup(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "\n".join(
            [
                "Settings lookup",
                "No approved engagement communities are ready for settings lookup.",
                "",
                "Approve an engagement target first, or open one directly with:",
                "/engagement_settings <community_id>",
            ]
        )
    return "\n".join(
        [
            f"Settings lookup ({offset + 1}-{offset + len(items)} of {total})",
            "Open a community below to review readiness, posting limits, quiet hours, and account assignment.",
            "",
            "Direct command: /engagement_settings <community_id>",
        ]
    )


def format_engagement_admin_advanced_home() -> str:
    return "\n".join(
        [
            "Advanced engagement",
            "Use these controls when you need prompt profiles, diagnostics, or audit detail.",
            "",
            "Prompt profiles: /engagement_prompts",
            "Semantic rollout: /engagement_rollout",
            "Audit and diagnostics: /engagement_actions",
        ]
    )


def format_engagement_targets(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    status = data.get("status")
    status_label = f" | {status}" if status else ""
    if not items:
        return (
            f"No engagement targets{status_label} in this view.\n\n"
            "Add one with /add_engagement_target <telegram_link_or_username_or_community_id>"
        )
    return "\n".join(
        [
            f"Engagement targets{status_label} ({offset + 1}-{offset + len(items)} of {total})",
            "Add: /add_engagement_target <telegram_link_or_username_or_community_id>",
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
    lines = [
        heading,
        f"Readiness: {_engagement_target_readiness(item)}",
        f"Status: {_target_status_label(item)}",
        (
            "Allowed: "
            f"watch/draft {_yes_no(item.get('allow_detect'))}, "
            f"join {_yes_no(item.get('allow_join'))}, "
            f"post reviewed replies {_yes_no(item.get('allow_post'))}"
        ),
    ]
    if item.get("submitted_ref"):
        lines.append(f"Submitted: {item['submitted_ref']}")
    if item.get("community_id"):
        lines.append(f"Settings: /engagement_settings {item['community_id']}")
    if item.get("community_id"):
        lines.append(f"Community: {item.get('community_title') or item['community_id']}")
    if item.get("notes"):
        lines.append(f"Notes: {_shorten(str(item['notes']), 240)}")
    if item.get("last_error"):
        lines.append(f"Error: {_shorten(str(item['last_error']), 240)}")
    if detail:
        lines.extend(
            [
                "",
                f"Target ID: {target_id}",
                f"Community ID: {item.get('community_id') or 'unresolved'}",
                f"Raw status: {item.get('status', 'unknown')}",
                (
                    "Raw permissions: "
                    f"allow_join={_yes_no(item.get('allow_join'))}, "
                    f"allow_detect={_yes_no(item.get('allow_detect'))}, "
                    f"allow_post={_yes_no(item.get('allow_post'))}"
                ),
            ]
        )
    lines.extend(["", *_engagement_target_next_actions(target_id, str(item.get("status") or "unknown"))])
    return "\n".join(lines)


def format_engagement_target_mutation(
    *,
    action: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> str:
    return "\n".join(
        [
            f"Engagement target {action}.",
            f"Before: {_target_permission_summary(before)}",
            f"After: {_target_permission_summary(after)}",
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
            "Confirm target approval",
            f"Target ID: {before.get('id', 'unknown')}",
            f"Community: {before.get('community_title') or before.get('community_id') or 'unresolved'}",
            f"Before: {_target_permission_summary(before)}",
            f"After: {_target_permission_summary(after)}",
            "",
            "Approval enables watching, joining, and reviewed public posting for this engagement target.",
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
            f"Confirm target {permission} permission change",
            f"Target ID: {before.get('id', 'unknown')}",
            f"Community: {before.get('community_title') or before.get('community_id') or 'unresolved'}",
            f"Before: {_target_permission_summary(before)}",
            f"After: {_target_permission_summary(after)}",
            "",
            "Posting remains public-reply only and still requires candidate approval before send.",
        ]
    )


def format_engagement_prompt_profiles(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "No engagement prompt profiles configured yet."
    return f"Engagement prompt profiles ({offset + 1}-{offset + len(items)} of {total})"


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
        heading,
        f"State: {active} | version {item.get('current_version_number') or 'none'}",
        f"Model: {item.get('model', 'unknown')} | temp {item.get('temperature', 0.2)} | max {item.get('max_output_tokens', 1000)}",
    ]
    if item.get("description"):
        lines.append(f"Description: {_shorten(str(item['description']), 180)}")
    if detail:
        lines.extend(
            [
                "",
                f"Profile ID: {profile_id}",
                f"Output schema: {item.get('output_schema_name', 'engagement_detection_v1')}",
            ]
        )
        if item.get("current_version_id"):
            lines.append(f"Current version ID: {item['current_version_id']}")
        if item.get("system_prompt"):
            lines.append(f"System: {_shorten(str(item['system_prompt']), 400)}")
        if item.get("user_prompt_template"):
            lines.append(f"User template: {_shorten(str(item['user_prompt_template']), 500)}")
    lines.extend(
        [
            f"Open: /engagement_prompt {profile_id}",
            f"Versions: /engagement_prompt_versions {profile_id}",
            f"Edit: /edit_engagement_prompt {profile_id} <field>",
            f"Duplicate: /duplicate_engagement_prompt {profile_id} <new name>",
        ]
    )
    lines.append(f"Preview: /engagement_prompt_preview {profile_id}")
    return "\n".join(lines)


def format_engagement_prompt_versions(data: dict[str, Any], *, profile_id: str) -> str:
    items = data.get("items") or []
    if not items:
        return f"No prompt profile versions found for {profile_id}."
    lines = [f"Prompt profile versions ({len(items)})", f"Profile ID: {profile_id}"]
    for item in items[:10]:
        lines.extend(
            [
                "",
                f"Version {item.get('version_number', 'unknown')}",
                f"Version ID: {item.get('id', 'unknown')}",
                f"Model: {item.get('model', 'unknown')} | temp {item.get('temperature', 0.2)} | max {item.get('max_output_tokens', 1000)}",
                f"Schema: {item.get('output_schema_name', 'engagement_detection_v1')}",
                f"Created by: {item.get('created_by', 'unknown')}",
                f"System: {_shorten(str(item.get('system_prompt') or ''), 240)}",
                f"User template: {_shorten(str(item.get('user_prompt_template') or ''), 280)}",
                f"Rollback: /rollback_engagement_prompt {profile_id} {item.get('version_number', 'unknown')}",
            ]
        )
    return "\n".join(lines)


def format_engagement_prompt_activation_confirmation(item: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Confirm prompt activation",
            f"Profile ID: {item.get('id', 'unknown')}",
            f"Name: {item.get('name', 'Prompt profile')}",
            f"Version: {item.get('current_version_number') or 'none'}",
            f"Model: {item.get('model', 'unknown')}",
            f"Temperature: {item.get('temperature', 0.2)}",
            f"Max output tokens: {item.get('max_output_tokens', 1000)}",
            f"Output schema: {item.get('output_schema_name', 'engagement_detection_v1')}",
            "",
            "Activation changes which prompt profile future engagement detection uses.",
        ]
    )


def format_engagement_prompt_rollback_confirmation(
    profile: dict[str, Any],
    version: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "Confirm prompt rollback",
            f"Profile ID: {profile.get('id', 'unknown')}",
            f"Name: {profile.get('name', 'Prompt profile')}",
            f"Rollback to version: {version.get('version_number', 'unknown')}",
            f"Version ID: {version.get('id', 'unknown')}",
            f"Model: {version.get('model', 'unknown')}",
            f"Temperature: {version.get('temperature', 0.2)}",
            f"Max output tokens: {version.get('max_output_tokens', 1000)}",
            f"Output schema: {version.get('output_schema_name', 'engagement_detection_v1')}",
            "",
            "Rollback creates a new immutable version from this older version.",
        ]
    )


def format_engagement_prompt_preview(data: dict[str, Any]) -> str:
    lines = [
        f"Prompt preview | {data.get('profile_name', 'profile')}",
        f"Model: {data.get('model', 'unknown')}",
        "",
        "System prompt:",
        _shorten(str(data.get("system_prompt") or ""), 900),
        "",
        "Rendered user prompt:",
        _shorten(str(data.get("rendered_user_prompt") or ""), 2400),
    ]
    return "\n".join(lines)


def format_engagement_style_rules(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "No engagement style rules in this view."
    scope_type = data.get("scope_type")
    scope_id = data.get("scope_id")
    scope_label = "all scopes"
    if scope_type:
        scope_label = str(scope_type)
        if scope_id:
            scope_label = f"{scope_label} {scope_id}"
    return f"Engagement style rules ({offset + 1}-{offset + len(items)} of {total}) | {scope_label}"


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
        heading,
        scope_line,
        f"Status: {'active' if item.get('active') else 'inactive'} | priority {item.get('priority', 100)}",
        f"Rule: {_shorten(str(item.get('rule_text') or ''), 500)}",
    ]
    if detail:
        lines.extend(
            [
                "",
                f"Rule ID: {rule_id}",
                f"Scope ID: {scope_id or '-'}",
            ]
        )
    lines.extend(
        [
        f"Open: /engagement_style_rule {rule_id}",
        f"Edit: /edit_style_rule {rule_id}",
        f"Toggle: /toggle_style_rule {rule_id} {'off' if item.get('active') else 'on'}",
        ]
    )
    return "\n".join(lines)


def format_engagement_settings(
    data: dict[str, Any],
    *,
    assigned_account_label: str | None = None,
) -> str:
    community_id = data.get("community_id", "unknown")
    title = data.get("community_title") or data.get("title") or data.get("community_name")
    lines = [
        f"Engagement settings | {title}" if title else "Engagement settings",
        f"Readiness: {_engagement_settings_readiness(data)}",
        f"Posting posture: {_settings_mode_label(data.get('mode'))}",
        f"Joining allowed: {_yes_no(data.get('allow_join'))}",
        f"Reviewed public replies allowed: {_yes_no(data.get('allow_post'))}",
        f"Safety floor: reply-only {_yes_no(data.get('reply_only'))}, approval required {_yes_no(data.get('require_approval'))}",
        (
            "Pacing: "
            f"{data.get('max_posts_per_day', 1)} per day, "
            f"{data.get('min_minutes_between_posts', 240)} minutes apart"
        ),
    ]
    if data.get("quiet_hours_start") or data.get("quiet_hours_end"):
        lines.append(
            "Quiet hours: "
            f"{_format_time_value(data.get('quiet_hours_start'))}-"
            f"{_format_time_value(data.get('quiet_hours_end'))}"
        )
    if data.get("assigned_account_id"):
        lines.append(
            "Engagement account: "
            f"{assigned_account_label or data['assigned_account_id']}"
        )
    else:
        lines.append("Engagement account: not assigned")
    lines.extend(
        [
            "",
            f"Community ID: {community_id}",
            f"Raw mode: {data.get('mode', 'disabled')}",
        ]
    )
    lines.extend(
        [
            "",
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
    return "\n".join(lines)


def format_engagement_account_assignment_confirmation(
    data: dict[str, Any],
    *,
    after_account_label: str,
    before_account_label: str,
) -> str:
    return "\n".join(
        [
            "Confirm engagement account assignment",
            f"Community ID: {data.get('community_id', 'unknown')}",
            f"Before: {before_account_label}",
            f"After: {after_account_label}",
            "",
            "The API will validate that the account belongs to the engagement pool before saving.",
        ]
    )


def format_engagement_topics(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "No engagement topics configured yet."
    active_count = sum(1 for item in items if item.get("active"))
    return f"Engagement topics ({offset + 1}-{offset + len(items)} of {total}) | active {active_count}"


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
        heading,
        f"Status: {'active' if item.get('active') else 'inactive'}",
    ]
    if detail:
        lines.append(f"Topic ID: {topic_id}")
    if item.get("description"):
        lines.append(f"Description: {_shorten(str(item['description']), 160)}")
    if keywords:
        lines.append(f"Notice: {_shorten(', '.join(str(value) for value in keywords), 160)}")
    if negative_keywords:
        lines.append(
            f"Avoid: {_shorten(', '.join(str(value) for value in negative_keywords), 160)}"
        )
    lines.append(f"Guidance: {_shorten(str(item.get('stance_guidance') or ''), 260)}")
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
        [
            f"Open: /engagement_topic {topic_id}",
            f"Edit guidance: /edit_topic_guidance {topic_id}",
            f"Edit triggers: /topic_keywords {topic_id} trigger <comma_keywords>",
            f"Edit negatives: /topic_keywords {topic_id} negative <comma_keywords>",
            f"Toggle: /toggle_engagement_topic {topic_id} {'off' if item.get('active') else 'on'}",
        ]
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
        f"{label} queued.",
        f"Job: {job_id} ({job.get('type', 'unknown')})",
        f"Status: {job.get('status', 'queued')}",
        f"Check it with /job {job_id}",
    ]
    if community_id:
        lines.append(f"Community: /community {community_id}")
    if candidate_id:
        lines.append(f"Candidate ID: {candidate_id}")
    return "\n".join(lines)


def format_engagement_actions(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "No engagement audit actions match this view."
    return f"Engagement audit ({offset + 1}-{offset + len(items)} of {total})"


def format_engagement_action_card(item: dict[str, Any], *, index: int | None = None) -> str:
    title = f"{item.get('action_type', 'action')} | {item.get('status', 'unknown')}"
    heading = f"{index}. {title}" if index is not None else title
    lines = [
        heading,
        f"Action ID: {item.get('id', 'unknown')}",
        f"Community ID: {item.get('community_id', 'unknown')}",
    ]
    if item.get("candidate_id"):
        lines.append(f"Candidate ID: {item['candidate_id']}")
    if item.get("reply_to_tg_message_id") is not None:
        lines.append(f"Reply to message: {item['reply_to_tg_message_id']}")
    if item.get("sent_tg_message_id") is not None:
        lines.append(f"Sent message: {item['sent_tg_message_id']}")
    if item.get("outbound_text"):
        lines.append(f"Outbound text: {_shorten(str(item['outbound_text']), 240)}")
    if item.get("error_message"):
        lines.append(f"Error: {_shorten(str(item['error_message']), 240)}")
    if item.get("created_at"):
        lines.append(f"Created: {item['created_at']}")
    if item.get("sent_at"):
        lines.append(f"Sent: {item['sent_at']}")
    return "\n".join(lines)


def format_engagement_semantic_rollout(data: dict[str, Any]) -> str:
    bands = data.get("bands") or []
    lines = [
        f"Semantic rollout | {data.get('window_days', 14)} days",
        f"Semantic replies: {data.get('total_semantic_candidates', 0)}",
        f"Reviewed: {data.get('reviewed_semantic_candidates', 0)}",
        (
            "Outcomes: "
            f"approved {data.get('approved', 0)}, "
            f"rejected {data.get('rejected', 0)}, "
            f"pending {data.get('pending', 0)}, "
            f"expired {data.get('expired', 0)}"
        ),
        f"Approval rate: {_percent(data.get('approval_rate'))}",
    ]
    if data.get("community_id"):
        lines.append(f"Community filter: {data['community_id']}")
    if data.get("topic_id"):
        lines.append(f"Topic filter: {data['topic_id']}")
    lines.extend(["", "Similarity bands"])

    populated = False
    for band in bands:
        total = int(band.get("total") or 0)
        if total <= 0:
            continue
        populated = True
        lines.append(
            (
                f"{band.get('label', 'band')}: {total} | "
                f"approved {band.get('approved', 0)}, "
                f"rejected {band.get('rejected', 0)}, "
                f"pending {band.get('pending', 0)}, "
                f"expired {band.get('expired', 0)} | "
                f"approval {_percent(band.get('approval_rate'))}"
            )
        )
    if not populated:
        lines.append("No semantic reply opportunities in this window.")
    return "\n".join(lines)


def format_engagement_candidates(
    data: dict[str, Any],
    *,
    offset: int = 0,
    status: str = "needs_review",
) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return f"No engagement replies with status {status} right now."

    return f"Engagement replies | {status} ({offset + 1}-{offset + len(items)} of {total})"


def format_engagement_candidate_card(item: dict[str, Any], *, index: int | None = None) -> str:
    title = item.get("community_title") or "Community"
    topic = item.get("topic_name") or "Topic"
    candidate_id = item.get("id", "unknown")
    status = str(item.get("status", "unknown"))
    source = _shorten(str(item.get("source_excerpt") or "No source excerpt recorded."), 500)
    reason = _shorten(str(item.get("detected_reason") or "No reason recorded."), 260)
    suggested = str(item.get("suggested_reply") or "No draft reply recorded.")
    final = item.get("final_reply")

    heading = f"{index}. {title}" if index is not None else title
    lines = [
        heading,
        f"Readiness: {_engagement_candidate_readiness(item)}",
        f"Topic: {topic}",
        f"Status: {status}",
        "",
        f"Source: {source}",
        f"Reason: {reason}",
        "",
        f"Suggested reply: {_shorten(suggested, 800)}",
    ]
    if final and final != suggested:
        lines.append(f"Final reply: {_shorten(str(final), 800)}")
    prompt_summary = item.get("prompt_render_summary") or {}
    if item.get("prompt_profile_version_id"):
        lines.append(
            "Prompt: "
            f"{prompt_summary.get('profile_name', 'profile')}#"
            f"{prompt_summary.get('version_number', '?')}"
        )
    risk_notes = item.get("risk_notes") or []
    if risk_notes:
        lines.append(f"Risk notes: {_shorten('; '.join(str(note) for note in risk_notes), 260)}")
    lines.extend(
        [
            "",
            f"Candidate ID: {candidate_id}",
        ]
    )
    lines.extend(_engagement_candidate_next_actions(candidate_id, status))
    return "\n".join(lines)


def format_engagement_candidate_review(action: str, item: dict[str, Any]) -> str:
    title = item.get("community_title") or "Community"
    candidate_id = item.get("id", "unknown")
    lines = [
        title,
        f"Candidate ID: {candidate_id}",
        f"Decision: {action}",
        f"Status: {item.get('status', 'unknown')}",
        f"Reviewed by: {item.get('reviewed_by') or 'operator'}",
    ]
    if item.get("status") == "approved":
        lines.append(f"Queue send: /send_reply {candidate_id}")
    return "\n".join(lines)


def format_engagement_candidate_revisions(data: dict[str, Any], *, candidate_id: str) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return f"No reply revisions for candidate {candidate_id} yet."

    lines = [f"Candidate revisions ({total})", f"Candidate ID: {candidate_id}"]
    for item in items[:10]:
        lines.extend(
            [
                "",
                f"Revision {item.get('revision_number', '?')}",
                f"Edited by: {item.get('edited_by') or 'operator'}",
            ]
        )
        if item.get("edit_reason"):
            lines.append(f"Reason: {_shorten(str(item['edit_reason']), 160)}")
        if item.get("created_at"):
            lines.append(f"Created: {item['created_at']}")
        lines.append(f"Reply: {_shorten(str(item.get('reply_text') or ''), 800)}")
    if len(items) > 10:
        lines.append(f"...and {len(items) - 10} more")
    return "\n".join(lines)
