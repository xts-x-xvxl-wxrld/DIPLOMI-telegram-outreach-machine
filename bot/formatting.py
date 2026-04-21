from __future__ import annotations

from typing import Any


def format_operator_cockpit() -> str:
    return "\n".join(
        [
            "Operator cockpit",
            "",
            "Discovery: import and review communities.",
            "Engagement: review replies and participation readiness.",
            "Accounts: check Telegram account health.",
            "Help: commands and upload format.",
        ]
    )


def format_discovery_cockpit(
    *,
    attention_count: int | None = None,
    review_count: int | None = None,
    watching_count: int | None = None,
    activity_count: int | None = None,
) -> str:
    lines = ["Discovery", ""]
    if review_count:
        lines.append(f"Next: Review {review_count} suggested communities.")
    elif attention_count:
        lines.append(f"Next: Check {attention_count} searches that need attention.")
    elif activity_count:
        lines.append(f"Next: Inspect {activity_count} jobs.")
    else:
        lines.append("Next: Start a search with example communities.")
    lines.append("")
    lines.append(f"Needs attention: {attention_count if attention_count is not None else '—'}")
    lines.append(f"Review communities: {review_count if review_count is not None else '—'}")
    if watching_count is not None:
        lines.append(f"Watching: {watching_count} communities")
    else:
        lines.append("Watching: —")
    if activity_count is not None:
        lines.append(f"Recent activity: {activity_count} jobs")
    else:
        lines.append("Recent activity: —")
    return "\n".join(lines)


def format_discovery_help() -> str:
    return "\n".join(
        [
            "Discovery help",
            "",
            "CSV upload columns: group_name, channel",
            "Optional CSV columns: title, notes",
            "Only public Telegram references are accepted.",
            "Private invite links are rejected.",
            "Direct handle intake: send @username or a public t.me link.",
            "No people search and no person-level scores.",
            "",
            "Commands:",
            "/seeds",
            "/seed <seed_group_id>",
            "/channels <seed_group_id>",
            "/candidates <seed_group_id>",
            "/community <community_id>",
            "/snapshot <community_id>",
            "/job <job_id>",
        ]
    )


def format_help() -> str:
    return "\n".join(
        [
            "Operator help",
            "",
            "CSV upload: group_name,channel",
            "Direct add: send @username or a public t.me link.",
            "",
            "Commands:",
            "/seeds — browse searches",
            "/seed <id> — open a search",
            "/engagement — engagement cockpit",
            "/engagement_admin — admin controls",
            "/accounts — account pool health",
            "/whoami — show your Telegram ID for allowlist onboarding",
            "/job <id> — check a background job",
            "",
            "Optional:",
            "/brief <description>",
        ]
    )


def format_start() -> str:
    return "\n".join(
        [
            "Telegram community discovery control surface is ready.",
            "",
            "Primary flow:",
            "1. Upload a CSV with group_name,channel columns",
            "2. Open seed groups with /seeds",
            "3. Resolve one group",
            "4. Review candidates inline",
            "",
            "Quick add:",
            "Send @username or a public t.me link to classify and save it.",
            "",
            "Core commands:",
            "/seeds",
            "/seed <seed_group_id>",
            "/channels <seed_group_id>",
            "/candidates <seed_group_id>",
            "/community <community_id>",
            "/snapshot <community_id>",
            "/members <community_id>",
            "/exportmembers <community_id>",
            "/engagement",
            "/engagement_admin",
            "/engagement_candidates",
            "/engagement_targets",
            "/engagement_target <target_id>",
            "/engagement_prompts",
            "/engagement_style",
            "/engagement_rollout",
            "/engagement_candidate <candidate_id>",
            "/approve_reply <candidate_id>",
            "/edit_reply <candidate_id> | <final_reply>",
            "/candidate_revisions <candidate_id>",
            "/expire_candidate <candidate_id>",
            "/retry_candidate <candidate_id>",
            "/reject_reply <candidate_id>",
            "/send_reply <candidate_id>",
            "/entity <intake_id>",
            "/job <job_id>",
            "/accounts",
            "/whoami",
            "",
            "Optional/future:",
            "/brief <audience description>",
        ]
    )


def format_briefs_unavailable() -> str:
    return (
        "Brief listing is still deferred. "
        "The active operator flow starts from seed-group CSV import."
    )


def format_created_brief(data: dict[str, Any]) -> str:
    brief = data.get("brief") or {}
    job = data.get("job") or {}
    brief_id = brief.get("id", "unknown")
    job_id = job.get("id", "unknown")
    job_type = job.get("type", "brief.process")
    return "\n".join(
        [
            "Optional brief queued.",
            f"Brief ID: {brief_id}",
            f"Processing job: {job_id} ({job_type})",
            "",
            f"Check it with /job {job_id}",
        ]
    )


def format_job_status(data: dict[str, Any]) -> str:
    lines = [
        "Job status",
        f"ID: {data.get('id', 'unknown')}",
        f"Type: {data.get('type') or 'unknown'}",
        f"Status: {data.get('status', 'unknown')}",
    ]
    if data.get("created_at"):
        lines.append(f"Created: {data['created_at']}")
    if data.get("started_at"):
        lines.append(f"Started: {data['started_at']}")
    if data.get("ended_at"):
        lines.append(f"Ended: {data['ended_at']}")
    if data.get("error"):
        lines.extend(["", f"Error: {_shorten(_last_error_line(str(data['error'])), 600)}"])
    return "\n".join(lines)


def format_candidates(
    data: dict[str, Any],
    *,
    seed_group_name: str | None = None,
    offset: int = 0,
) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        target = f" for {seed_group_name}" if seed_group_name else ""
        return f"No candidate communities{target} yet."

    heading = "Candidate communities"
    if seed_group_name:
        heading = f"{heading} | {seed_group_name}"
    return f"{heading} ({offset + 1}-{offset + len(items)} of {total})"


def format_candidate_card(item: dict[str, Any], *, index: int | None = None) -> str:
    community = _candidate_community(item)
    title = community.get("title") or community.get("username") or "Untitled community"
    username = community.get("username")
    member_count = community.get("member_count")
    status = community.get("status", "unknown")
    reason = community.get("match_reason") or "No match reason recorded yet."
    community_id = community.get("id", "unknown")
    source_seed_count = item.get("source_seed_count")
    evidence_count = item.get("evidence_count")
    evidence_types = item.get("evidence_types") or []

    heading = f"{index}. {title}" if index is not None else title
    lines = [heading, f"Status: {status}"]
    if username:
        lines.append(f"Link: https://t.me/{username}")
    if member_count is not None:
        lines.append(f"Members: {member_count}")
    if source_seed_count is not None or evidence_count is not None:
        evidence_summary = (
            f"Evidence: seeds {source_seed_count or 0}, edges {evidence_count or 0}"
        )
        if evidence_types:
            evidence_summary = (
                f"{evidence_summary} | {', '.join(str(value) for value in evidence_types)}"
            )
        lines.append(evidence_summary)
    lines.extend(
        [
            f"Reason: {_shorten(str(reason), 240)}",
            f"Community ID: {community_id}",
        ]
    )
    return "\n".join(lines)


def format_review(decision: str, data: dict[str, Any]) -> str:
    community = data.get("community") or {}
    job = data.get("job")
    title = community.get("title") or community.get("username") or "Community"
    lines = [
        f"{title}",
        f"Decision: {decision}",
        f"Status: {community.get('status', 'unknown')}",
        f"Community ID: {community.get('id', 'unknown')}",
    ]
    if isinstance(job, dict):
        lines.extend(
            [
                "",
                f"Snapshot job: {job.get('id', 'unknown')} "
                f"({job.get('type', 'community.snapshot')})",
                f"Check it with /job {job.get('id', 'unknown')}",
            ]
        )
    return "\n".join(lines)


def format_accounts(data: dict[str, Any]) -> str:
    counts = data.get("counts") or {}
    lines = [
        "Telegram account pool",
        (
            "Counts: "
            f"available={counts.get('available', 0)}, "
            f"in_use={counts.get('in_use', 0)}, "
            f"rate_limited={counts.get('rate_limited', 0)}, "
            f"banned={counts.get('banned', 0)}"
        ),
    ]
    items = data.get("items") or []
    if items:
        lines.append("")
    for account in items[:10]:
        line = f"{account.get('phone', 'masked')} - {account.get('status', 'unknown')}"
        if account.get("flood_wait_until"):
            line = f"{line} until {account['flood_wait_until']}"
        lines.append(line)
    if len(items) > 10:
        lines.append(f"...and {len(items) - 10} more")
    return "\n".join(lines)


def format_seed_import(data: dict[str, Any]) -> str:
    imported = data.get("imported", 0)
    updated = data.get("updated", 0)
    errors = data.get("errors") or []
    groups = data.get("groups") or []

    lines = [
        "Seed CSV imported.",
        f"Imported: {imported}",
        f"Updated: {updated}",
    ]
    if groups:
        lines.extend(["", "Groups:"])
        for group in groups[:10]:
            group_id = group.get("id", "unknown")
            lines.append(
                f"- {group.get('name', 'unknown')} ({group_id}) | "
                f"+{group.get('imported', 0)}, updated {group.get('updated', 0)}"
            )
            lines.append(f"  Open: /seed {group_id}")
    if errors:
        lines.extend(["", f"Skipped rows: {len(errors)}"])
        for error in errors[:5]:
            lines.append(f"Row {error.get('row_number', '?')}: {error.get('message', 'invalid')}")
        if len(errors) > 5:
            lines.append(f"...and {len(errors) - 5} more")
    lines.extend(["", "List all groups with /seeds"])
    return "\n".join(lines)


def format_seed_groups(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "No seed groups yet. Upload a CSV with group_name,channel columns."

    lines = [f"Seed groups ({total})", "Open any group card below or use /seed <seed_group_id>."]
    return "\n".join(lines)


def format_seed_group_card(group: dict[str, Any]) -> str:
    group_id = group.get("id", "unknown")
    return "\n".join(
        [
            f"{group.get('name', 'Unnamed group')}",
            f"ID: {group_id}",
            (
                f"Seeds: {group.get('seed_count', 0)} | "
                f"unresolved {group.get('unresolved_count', 0)}, "
                f"resolved {group.get('resolved_count', 0)}, "
                f"failed {group.get('failed_count', 0)}"
            ),
            f"Open: /seed {group_id}",
        ]
    )


def format_seed_group(data: dict[str, Any]) -> str:
    group = data.get("group") or {}
    group_id = group.get("id", "unknown")
    return "\n".join(
        [
            f"{group.get('name', 'Unnamed group')}",
            f"ID: {group_id}",
            (
                f"Seeds: {group.get('seed_count', 0)} | "
                f"unresolved {group.get('unresolved_count', 0)}, "
                f"resolved {group.get('resolved_count', 0)}, "
                f"failed {group.get('failed_count', 0)}"
            ),
            f"Channels: /channels {group_id}",
            f"Candidates: /candidates {group_id}",
            f"Resolve: /resolveseeds {group_id}",
        ]
    )


def format_seed_channels(
    data: dict[str, Any],
    *,
    group_name: str | None = None,
    offset: int = 0,
    page_size: int = 5,
) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        target = f" for {group_name}" if group_name else ""
        return f"No imported seed channels{target}."

    page = items[offset : offset + page_size]
    heading = "Seed channels"
    if group_name:
        heading = f"{heading} | {group_name}"
    lines = [f"{heading} ({offset + 1}-{offset + len(page)} of {total})"]
    for item in page:
        label = item.get("title") or item.get("username") or item.get("raw_value", "seed")
        lines.extend(
            [
                "",
                f"{label}",
                f"Status: {item.get('status', 'unknown')}",
            ]
        )
        if item.get("telegram_url"):
            lines.append(f"Link: {item['telegram_url']}")
        if item.get("community_id"):
            lines.append(f"Community: /community {item['community_id']}")
    return "\n".join(lines)


def format_seed_group_resolution(data: dict[str, Any]) -> str:
    job = data.get("job") or {}
    job_id = job.get("id", "unknown")
    return "\n".join(
        [
            "Seed group resolution queued. Resolved communities will queue initial snapshots.",
            f"Job: {job_id} ({job.get('type', 'seed.resolve')})",
            f"Status: {job.get('status', 'queued')}",
            f"Check it with /job {job_id}",
        ]
    )


def format_telegram_entity_submission(data: dict[str, Any]) -> str:
    intake = data.get("intake") or {}
    job = data.get("job") or {}
    job_id = job.get("id", "unknown")
    intake_id = intake.get("id", "unknown")
    lines = [
        "Telegram entity classification queued.",
        f"Submitted: {intake.get('telegram_url') or intake.get('raw_value', 'unknown')}",
        f"Intake ID: {intake_id}",
        f"Job: {job_id} ({job.get('type', 'telegram_entity.resolve')})",
        f"Check it with /job {job_id}",
        f"Result: /entity {intake_id}",
    ]
    return "\n".join(lines)


def format_telegram_entity_intake(data: dict[str, Any]) -> str:
    entity_type = data.get("entity_type") or "pending"
    lines = [
        "Telegram entity intake",
        f"ID: {data.get('id', 'unknown')}",
        f"Submitted: {data.get('telegram_url') or data.get('raw_value', 'unknown')}",
        f"Status: {data.get('status', 'unknown')}",
        f"Type: {entity_type}",
    ]
    if data.get("community_id"):
        lines.append(f"Community: /community {data['community_id']}")
    if data.get("user_id"):
        lines.append(f"User row ID: {data['user_id']}")
    if data.get("error_message"):
        lines.append(f"Error: {_shorten(str(data['error_message']), 240)}")
    return "\n".join(lines)


def format_snapshot_job(data: dict[str, Any], *, community_title: str | None = None) -> str:
    job = data.get("job") or {}
    label = community_title or "Community snapshot"
    job_id = job.get("id", "unknown")
    return "\n".join(
        [
            f"{label}",
            f"Snapshot job: {job_id} ({job.get('type', 'community.snapshot')})",
            f"Status: {job.get('status', 'queued')}",
            f"Check it with /job {job_id}",
        ]
    )


def format_members(
    data: dict[str, Any],
    *,
    community_title: str | None = None,
    offset: int = 0,
) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    label = community_title or "Community"
    if not items:
        return f"No snapshotted visible members for {label} yet."

    lines = [f"Visible members | {label} ({offset + 1}-{offset + len(items)} of {total})"]
    for index, member in enumerate(items, start=offset + 1):
        name = member.get("username") or member.get("first_name") or str(member.get("tg_user_id", "unknown"))
        lines.extend(
            [
                "",
                f"{index}. {name}",
                f"Telegram user ID: {member.get('tg_user_id', 'unknown')}",
                f"Membership: {member.get('membership_status', 'member')}",
                f"Activity: {member.get('activity_status', 'unknown')}",
            ]
        )
        if member.get("username"):
            lines.append(f"Public username: @{member['username']}")
        if member.get("first_seen_at"):
            lines.append(f"First seen: {member['first_seen_at']}")
        if member.get("last_active_at"):
            lines.append(f"Last active: {member['last_active_at']}")
    return "\n".join(lines)


def format_member_export(data: dict[str, Any], *, community_title: str | None = None) -> str:
    label = community_title or "community"
    total = data.get("total", len(data.get("items") or []))
    return f"Exported {total} visible members for {label}."


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
            "Open a community first, then tune its posting limits and engagement account.",
            "",
            "Settings lookup: /engagement_settings <community_id>",
            "Communities: /engagement_targets",
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


def format_engagement_target_card(item: dict[str, Any], *, index: int | None = None) -> str:
    target_id = item.get("id", "unknown")
    label = item.get("community_title") or item.get("submitted_ref") or "Target"
    heading = f"{index}. {label}" if index is not None else str(label)
    lines = [
        heading,
        f"Readiness: {_engagement_target_readiness(item)}",
        "",
        f"Target ID: {target_id}",
        f"Submitted: {item.get('submitted_ref', 'unknown')}",
        f"Status: {item.get('status', 'unknown')}",
        (
            "Permissions: "
            f"join={_yes_no(item.get('allow_join'))}, "
            f"detect={_yes_no(item.get('allow_detect'))}, "
            f"post={_yes_no(item.get('allow_post'))}"
        ),
    ]
    if item.get("community_id"):
        lines.append(f"Community ID: {item['community_id']}")
    if item.get("notes"):
        lines.append(f"Notes: {_shorten(str(item['notes']), 240)}")
    if item.get("last_error"):
        lines.append(f"Error: {_shorten(str(item['last_error']), 240)}")
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
            format_engagement_target_card(after),
        ]
    )


def format_engagement_prompt_profiles(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "No engagement prompt profiles configured yet."
    return f"Engagement prompt profiles ({offset + 1}-{offset + len(items)} of {total})"


def format_engagement_prompt_profile_card(item: dict[str, Any], *, index: int | None = None) -> str:
    profile_id = item.get("id", "unknown")
    name = item.get("name") or "Prompt profile"
    heading = f"{index}. {name}" if index is not None else str(name)
    active = "active" if item.get("active") else "inactive"
    lines = [
        heading,
        f"Profile ID: {profile_id}",
        f"Status: {active}",
        f"Version: {item.get('current_version_number') or 'none'}",
        f"Model: {item.get('model', 'unknown')} | temp {item.get('temperature', 0.2)} | max {item.get('max_output_tokens', 1000)}",
        f"Output schema: {item.get('output_schema_name', 'engagement_detection_v1')}",
    ]
    if item.get("description"):
        lines.append(f"Description: {_shorten(str(item['description']), 180)}")
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
    return f"Engagement style rules ({offset + 1}-{offset + len(items)} of {total})"


def format_engagement_style_rule_card(item: dict[str, Any], *, index: int | None = None) -> str:
    rule_id = item.get("id", "unknown")
    heading = f"{index}. {item.get('name') or 'Style rule'}" if index is not None else str(item.get("name") or "Style rule")
    lines = [
        heading,
        f"Rule ID: {rule_id}",
        f"Scope: {item.get('scope_type', 'global')} {item.get('scope_id') or ''}".rstrip(),
        f"Status: {'active' if item.get('active') else 'inactive'} | priority {item.get('priority', 100)}",
        f"Rule: {_shorten(str(item.get('rule_text') or ''), 500)}",
    ]
    return "\n".join(lines)


def format_engagement_settings(data: dict[str, Any]) -> str:
    community_id = data.get("community_id", "unknown")
    lines = [
        "Engagement settings",
        f"Readiness: {_engagement_settings_readiness(data)}",
        "",
        f"Community ID: {community_id}",
        f"Mode: {data.get('mode', 'disabled')}",
        f"Join allowed: {_yes_no(data.get('allow_join'))}",
        f"Post allowed: {_yes_no(data.get('allow_post'))}",
        f"Reply only: {_yes_no(data.get('reply_only'))}",
        f"Approval required: {_yes_no(data.get('require_approval'))}",
        (
            "Rate limit: "
            f"{data.get('max_posts_per_day', 1)} per day, "
            f"{data.get('min_minutes_between_posts', 240)} minutes apart"
        ),
    ]
    if data.get("quiet_hours_start") or data.get("quiet_hours_end"):
        lines.append(
            "Quiet hours: "
            f"{data.get('quiet_hours_start') or '?'}-"
            f"{data.get('quiet_hours_end') or '?'}"
        )
    if data.get("assigned_account_id"):
        lines.append(f"Assigned account ID: {data['assigned_account_id']}")
    lines.extend(
        [
            "",
            f"Preset: /set_engagement {community_id} <off|observe|suggest|ready>",
            f"Join: /join_community {community_id}",
            f"Detect: /detect_engagement {community_id}",
        ]
    )
    return "\n".join(lines)


def format_engagement_topics(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "No engagement topics configured yet."
    active_count = sum(1 for item in items if item.get("active"))
    return f"Engagement topics ({offset + 1}-{offset + len(items)} of {total}) | active {active_count}"


def format_engagement_topic_card(item: dict[str, Any], *, index: int | None = None) -> str:
    topic_id = item.get("id", "unknown")
    name = item.get("name") or "Untitled topic"
    heading = f"{index}. {name}" if index is not None else str(name)
    keywords = item.get("trigger_keywords") or []
    negative_keywords = item.get("negative_keywords") or []
    lines = [
        heading,
        f"Status: {'active' if item.get('active') else 'inactive'}",
        f"Topic ID: {topic_id}",
    ]
    if item.get("description"):
        lines.append(f"Description: {_shorten(str(item['description']), 160)}")
    if keywords:
        lines.append(f"Triggers: {_shorten(', '.join(str(value) for value in keywords), 160)}")
    if negative_keywords:
        lines.append(
            f"Negative keywords: {_shorten(', '.join(str(value) for value in negative_keywords), 160)}"
        )
    lines.extend(
        [
            f"Guidance: {_shorten(str(item.get('stance_guidance') or ''), 260)}",
            f"Toggle: /toggle_engagement_topic {topic_id} {'off' if item.get('active') else 'on'}",
        ]
    )
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


def format_community_detail(
    detail: dict[str, Any],
    snapshot_runs: dict[str, Any] | None = None,
) -> str:
    community = detail.get("community") or {}
    latest_snapshot = detail.get("latest_snapshot") or {}
    latest_analysis = detail.get("latest_analysis") or {}
    latest_run = ((snapshot_runs or {}).get("items") or [None])[0] or {}
    title = community.get("title") or community.get("username") or "Community"
    lines = [
        f"{title}",
        f"Community ID: {community.get('id', 'unknown')}",
        f"Status: {community.get('status', 'unknown')}",
    ]
    if community.get("username"):
        lines.append(f"Link: https://t.me/{community['username']}")
    if community.get("source"):
        lines.append(f"Source: {community['source']}")
    if community.get("member_count") is not None:
        lines.append(f"Members: {community['member_count']}")
    if community.get("match_reason"):
        lines.append(f"Reason: {_shorten(str(community['match_reason']), 240)}")

    if latest_snapshot:
        lines.extend(
            [
                "",
                "Latest snapshot",
                f"Snapshotted: {latest_snapshot.get('collected_at', 'unknown')}",
                f"Member count: {latest_snapshot.get('member_count', 'unknown')}",
                f"Messages 7d: {latest_snapshot.get('message_count_7d', 'unknown')}",
            ]
        )

    if latest_run:
        lines.extend(
            [
                "",
                "Latest snapshot run",
                f"Status: {latest_run.get('status', 'unknown')}",
                f"Analysis: {latest_run.get('analysis_status', 'unknown')}",
                f"Window: {latest_run.get('window_days', 'unknown')} days",
                f"Members seen: {latest_run.get('members_seen', 'unknown')}",
                f"Messages seen: {latest_run.get('messages_seen', 'unknown')}",
            ]
        )

    if latest_analysis:
        lines.extend(
            [
                "",
                "Latest analysis",
                f"Analyzed: {latest_analysis.get('analyzed_at', 'unknown')}",
            ]
        )
        if latest_analysis.get("summary"):
            lines.append(f"Summary: {_shorten(str(latest_analysis['summary']), 240)}")
        themes = latest_analysis.get("dominant_themes") or []
        if themes:
            lines.append(f"Themes: {', '.join(str(theme) for theme in themes[:5])}")
        if latest_analysis.get("activity_level"):
            lines.append(f"Activity: {latest_analysis['activity_level']}")
        if latest_analysis.get("centrality"):
            lines.append(f"Centrality: {latest_analysis['centrality']}")
        if latest_analysis.get("relevance_notes"):
            lines.append(
                f"Relevance: {_shorten(str(latest_analysis['relevance_notes']), 180)}"
            )

    return "\n".join(lines)


def format_api_error(message: str) -> str:
    return f"API error: {message}"


def format_whoami(user_id: int, username: str | None = None) -> str:
    lines = [
        "Telegram identity",
        f"User ID: {user_id}",
    ]
    if username:
        lines.append(f"Username: @{username}")
    lines.extend(
        [
            "",
            "Give this User ID to the operator so it can be added to TELEGRAM_ALLOWED_USER_IDS.",
        ]
    )
    return "\n".join(lines)


def format_access_denied(user_id: int | None, username: str | None = None) -> str:
    lines = ["This bot is restricted."]
    if user_id is not None:
        lines.append(f"Your Telegram user ID: {user_id}")
    if username:
        lines.append(f"Username: @{username}")
    if user_id is not None:
        lines.append("Ask the operator to add this ID to TELEGRAM_ALLOWED_USER_IDS.")
    return "\n".join(lines)


def _engagement_candidate_readiness(item: dict[str, Any]) -> str:
    readiness = item.get("readiness") or item.get("send_readiness")
    if readiness:
        return str(readiness)

    status = str(item.get("status") or "unknown")
    if status == "needs_review":
        return "Needs review"
    if status == "approved":
        return "Approved, ready to send"
    if status == "failed":
        return "Failed, retry may be available"
    if status == "sent":
        return "Sent"
    if status == "rejected":
        return "Rejected"
    if status == "expired":
        return "Blocked: reply expired"
    return status.replace("_", " ").title()


def _engagement_candidate_next_actions(candidate_id: str, status: str) -> list[str]:
    if status == "needs_review":
        return [
            f"Open: /engagement_candidate {candidate_id}",
            f"Edit: /edit_reply {candidate_id} | <final reply>",
            f"Approve: /approve_reply {candidate_id}",
            f"Reject: /reject_reply {candidate_id}",
            f"Expire: /expire_candidate {candidate_id}",
        ]
    if status == "approved":
        return [
            f"Open: /engagement_candidate {candidate_id}",
            f"Send: /send_reply {candidate_id}",
            f"Edit: /edit_reply {candidate_id} | <final reply>",
            f"Reject: /reject_reply {candidate_id}",
            f"Expire: /expire_candidate {candidate_id}",
        ]
    if status == "failed":
        return [
            f"Open: /engagement_candidate {candidate_id}",
            f"Retry: /retry_candidate {candidate_id}",
            f"Edit: /edit_reply {candidate_id} | <final reply>",
            f"Reject: /reject_reply {candidate_id}",
            f"Expire: /expire_candidate {candidate_id}",
        ]
    if status in {"sent", "rejected", "expired"}:
        return [
            f"Open: /engagement_candidate {candidate_id}",
            f"Revisions: /candidate_revisions {candidate_id}",
            "Audit: /engagement_actions",
        ]
    return [
        f"Open: /engagement_candidate {candidate_id}",
        f"Edit: /edit_reply {candidate_id} | <final reply>",
        f"Reject: /reject_reply {candidate_id}",
    ]


def _engagement_target_readiness(item: dict[str, Any]) -> str:
    readiness = item.get("readiness") or item.get("community_readiness")
    if readiness:
        return str(readiness)

    status = str(item.get("status") or "unknown")
    allow_detect = bool(item.get("allow_detect"))
    allow_post = bool(item.get("allow_post"))
    allow_join = bool(item.get("allow_join"))

    if status in {"pending", "resolved"}:
        return "Not approved"
    if status == "failed":
        return "Blocked: target failed to resolve"
    if status in {"rejected", "archived"}:
        return "Paused"
    if status != "approved":
        return status.replace("_", " ").title()
    if allow_post:
        return "Ready to post with review"
    if allow_detect:
        return "Drafting replies"
    if allow_join:
        return "Approved, not joined"
    return "Watching only"


def _engagement_target_next_actions(target_id: str, status: str) -> list[str]:
    actions = [f"Open: /engagement_target {target_id}"]
    if status in {"pending", "failed"}:
        actions.append(f"Resolve: /resolve_engagement_target {target_id}")
    if status == "resolved":
        actions.append(f"Approve: /approve_engagement_target {target_id}")
    if status == "approved":
        actions.extend(
            [
                f"Watch/draft: /target_permission {target_id} detect <on|off>",
                f"Posting: /target_permission {target_id} post <on|off>",
                f"Joining: /target_permission {target_id} join <on|off>",
                f"Join: /target_join {target_id}",
                f"Detect: /target_detect {target_id}",
            ]
        )
    if status not in {"rejected", "archived"}:
        actions.append(f"Reject: /reject_engagement_target {target_id}")
        actions.append(f"Archive: /archive_engagement_target {target_id}")
    return actions


def _target_permission_summary(item: dict[str, Any]) -> str:
    return (
        f"status={item.get('status', 'unknown')}, "
        f"join={_yes_no(item.get('allow_join'))}, "
        f"detect={_yes_no(item.get('allow_detect'))}, "
        f"post={_yes_no(item.get('allow_post'))}"
    )


def _engagement_settings_readiness(data: dict[str, Any]) -> str:
    readiness = data.get("readiness") or data.get("community_readiness")
    if readiness:
        return str(readiness)

    mode = str(data.get("mode") or "disabled")
    allow_post = bool(data.get("allow_post"))
    allow_join = bool(data.get("allow_join"))

    if mode == "disabled":
        return "Paused"
    if mode == "observe":
        return "Watching only"
    if allow_post:
        return "Ready to post with review"
    if mode in {"suggest", "require_approval"}:
        return "Drafting replies"
    if allow_join:
        return "Approved, not joined"
    return "Blocked: posting permission off"


def _candidate_community(item: dict[str, Any]) -> dict[str, Any]:
    community = item.get("community")
    if isinstance(community, dict):
        return community
    return item


def _last_error_line(error: str) -> str:
    lines = [line.strip() for line in error.splitlines() if line.strip()]
    return lines[-1] if lines else error


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _percent(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "n/a"
