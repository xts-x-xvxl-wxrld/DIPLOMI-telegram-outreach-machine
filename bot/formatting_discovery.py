from __future__ import annotations

from typing import Any

from .formatting_common import (
    _action_block,
    _bullet,
    _candidate_community,
    _field,
    _headline,
    _last_error_line,
    _section,
    _shorten,
    _status_icon,
)


def format_operator_cockpit() -> str:
    return "\n".join(
        [
            _headline("Operator cockpit", icon="🧭"),
            "",
            _bullet("Discovery: import and review communities.", icon="🔎"),
            _bullet("Engagement: review replies and participation readiness.", icon="💬"),
            _bullet("Accounts: check Telegram account health.", icon="📲"),
            _bullet("Help: commands and upload format.", icon="❓"),
        ]
    )


def format_discovery_cockpit(
    *,
    attention_count: int | None = None,
    review_count: int | None = None,
    watching_count: int | None = None,
    activity_count: int | None = None,
) -> str:
    lines = [_headline("Discovery", icon="🔎"), ""]
    if review_count:
        lines.append(_bullet(f"Review {review_count} suggested communities next.", icon="➡"))
    elif attention_count:
        lines.append(_bullet(f"Check {attention_count} searches that need attention next.", icon="➡"))
    elif activity_count:
        lines.append(_bullet(f"Inspect {activity_count} recent jobs next.", icon="➡"))
    else:
        lines.append(_bullet("Start a search from example communities.", icon="➡"))
    lines.extend(
        [
            "",
            _section("Queue", icon="📊"),
            _field("Needs attention", attention_count if attention_count is not None else "--"),
            _field("Review communities", review_count if review_count is not None else "--"),
            _field(
                "Watching",
                f"{watching_count} communities" if watching_count is not None else "--",
            ),
            _field(
                "Recent activity",
                f"{activity_count} jobs" if activity_count is not None else "--",
            ),
        ]
    )
    return "\n".join(lines)


def format_discovery_help() -> str:
    return "\n".join(
        [
            _headline("Discovery help", icon="🧠"),
            "",
            _section("Import rules", icon="📥"),
            _bullet("CSV upload columns: group_name, channel"),
            _bullet("Optional CSV columns: title, notes"),
            _bullet("Only public Telegram references are accepted."),
            _bullet("Private invite links are rejected.", icon="⛔"),
            _bullet("Direct handle intake: send @username or a public t.me link."),
            _bullet("No people search and no person-level scores.", icon="🛡"),
            "",
            _section("Commands", icon="⌨"),
            "/search <plain language query>",
            "/searches",
            "/search_run <search_run_id>",
            "/search_candidates <search_run_id>",
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
            _headline("Operator help", icon="❓"),
            "",
            _section("Quick start", icon="🚀"),
            _bullet("CSV upload: group_name,channel"),
            _bullet("Direct add: send @username or a public t.me link."),
            "",
            _section("Commands", icon="⌨"),
            "/search <query> - start a community search",
            "/searches - recent community searches",
            "/seeds - browse searches",
            "/seed <id> - open a search",
            "/engagement - engagement cockpit",
            "/engagement_admin - admin controls",
            "/accounts - account pool health",
            "/add_account <search|engagement> <phone> [session_name] [notes...]",
            "/whoami - show your Telegram ID for allowlist onboarding",
            "/job <id> - check a background job",
            "",
            _section("Optional", icon="🧪"),
            "/brief <description>",
        ]
    )


def format_start() -> str:
    return "\n".join(
        [
            _headline("Telegram community discovery control surface is ready.", icon="✨"),
            "",
            _section("Primary flow", icon="🧭"),
            "1. Upload a CSV with group_name,channel columns",
            "2. Open seed groups with /seeds",
            "3. Resolve one group",
            "4. Review candidates inline",
            "",
            _section("Quick add", icon="➕"),
            "Send @username or a public t.me link to classify and save it.",
            "",
            _section("Core commands", icon="⌨"),
            "/search <plain language query>",
            "/searches",
            "/search_run <search_run_id>",
            "/search_candidates <search_run_id>",
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
            "/create_engagement_prompt <name> | <description_or_dash> | <model> | <temperature> | <max_output_tokens> | <system_prompt> | <user_prompt_template>",
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
            "/add_account <search|engagement> <phone> [session_name] [notes...]",
            "/whoami",
            "",
            _section("Optional/future", icon="🧪"),
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
            _headline("Optional brief queued.", icon="📝"),
            _field("Brief ID", brief_id),
            _field("Processing job", f"{job_id} ({job_type})"),
            *_action_block([f"Check it with /job {job_id}"]),
        ]
    )


def format_job_status(data: dict[str, Any]) -> str:
    lines = [
        _headline("Job status", icon="🕒"),
        _field("ID", data.get("id", "unknown")),
        _field("Type", data.get("type") or "unknown"),
        _field("Status", data.get("status", "unknown"), icon=_status_icon(data.get("status"))),
    ]
    if data.get("created_at"):
        lines.append(_field("Created", data["created_at"]))
    if data.get("started_at"):
        lines.append(_field("Started", data["started_at"]))
    if data.get("ended_at"):
        lines.append(_field("Ended", data["ended_at"]))
    if data.get("error"):
        lines.extend(["", _field("Error", _shorten(_last_error_line(str(data["error"])), 600), icon="⛔")])
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
        return _headline(f"No candidate communities{target} yet.", icon="📭")

    heading = "Candidate communities"
    if seed_group_name:
        heading = f"{heading} | {seed_group_name}"
    return _headline(f"{heading} ({offset + 1}-{offset + len(items)} of {total})", icon="🧩")


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
    lines = [
        _headline(heading, icon="🧩"),
        _field("Status", status, icon=_status_icon(status)),
    ]
    if username:
        lines.append(_field("Link", f"https://t.me/{username}", icon="🔗"))
    if member_count is not None:
        lines.append(_field("Members", member_count, icon="👥"))
    if source_seed_count is not None or evidence_count is not None:
        evidence_summary = f"Evidence: seeds {source_seed_count or 0}, edges {evidence_count or 0}"
        if evidence_types:
            evidence_summary = f"{evidence_summary} | {', '.join(str(value) for value in evidence_types)}"
        lines.append(_bullet(evidence_summary, icon="🕸"))
    lines.extend(
        [
            "",
            _section("Why it matched", icon="📝"),
            _bullet(_shorten(str(reason), 240)),
            "",
            _field("Community ID", community_id, icon="🆔"),
        ]
    )
    return "\n".join(lines)


def format_review(decision: str, data: dict[str, Any]) -> str:
    community = data.get("community") or {}
    job = data.get("job")
    title = community.get("title") or community.get("username") or "Community"
    lines = [
        _headline(title, icon="✅" if decision == "approve" else "📝"),
        _field("Decision", decision),
        _field("Status", community.get("status", "unknown"), icon=_status_icon(community.get("status"))),
        _field("Community ID", community.get("id", "unknown"), icon="🆔"),
    ]
    if isinstance(job, dict):
        lines.extend(
            [
                "",
                _section("Snapshot queued", icon="📸"),
                _field(
                    "Snapshot job",
                    f"{job.get('id', 'unknown')} ({job.get('type', 'community.snapshot')})",
                ),
                _bullet(f"Check it with /job {job.get('id', 'unknown')}", icon="➡"),
            ]
        )
    return "\n".join(lines)


def format_accounts(data: dict[str, Any]) -> str:
    counts = data.get("counts") or {}
    pool_counts = data.get("counts_by_pool") or {}
    lines = [
        _headline("Telegram account pool", icon="📲"),
        _field(
            "Counts",
            (
                f"available={counts.get('available', 0)}, "
                f"in_use={counts.get('in_use', 0)}, "
                f"rate_limited={counts.get('rate_limited', 0)}, "
                f"banned={counts.get('banned', 0)}"
            ),
        ),
        _field(
            "Pools",
            (
                f"search={pool_counts.get('search', 0)}, "
                f"engagement={pool_counts.get('engagement', 0)}, "
                f"disabled={pool_counts.get('disabled', 0)}"
            ),
        ),
    ]
    items = data.get("items") or []
    if items:
        lines.extend(["", _section("Accounts", icon="📋")])
    for account in items[:10]:
        line = f"{account.get('phone', 'masked')} - {account.get('status', 'unknown')}"
        if account.get("account_pool"):
            line = f"{line} - {account['account_pool']}"
        if account.get("flood_wait_until"):
            line = f"{line} until {account['flood_wait_until']}"
        lines.append(_bullet(line))
    if len(items) > 10:
        lines.append(_bullet(f"...and {len(items) - 10} more"))
    return "\n".join(lines)


def format_seed_import(data: dict[str, Any]) -> str:
    imported = data.get("imported", 0)
    updated = data.get("updated", 0)
    errors = data.get("errors") or []
    groups = data.get("groups") or []

    lines = [
        _headline("Seed CSV imported.", icon="📥"),
        _field("Imported", imported),
        _field("Updated", updated),
    ]
    if groups:
        lines.extend(["", _section("Groups", icon="🌱")])
        for group in groups[:10]:
            group_id = group.get("id", "unknown")
            lines.append(
                _bullet(
                    f"{group.get('name', 'unknown')} ({group_id}) | +{group.get('imported', 0)}, "
                    f"updated {group.get('updated', 0)}"
                )
            )
            lines.append(_bullet(f"Open: /seed {group_id}", icon="  ->"))
    if errors:
        lines.extend(["", _field("Skipped rows", len(errors), icon="⚠")])
        for error in errors[:5]:
            lines.append(_bullet(f"Row {error.get('row_number', '?')}: {error.get('message', 'invalid')}"))
        if len(errors) > 5:
            lines.append(_bullet(f"...and {len(errors) - 5} more"))
    lines.extend(_action_block(["List all groups with /seeds"]))
    return "\n".join(lines)


def format_seed_groups(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return _headline("No seed groups yet. Upload a CSV with group_name,channel columns.", icon="📭")

    return "\n".join(
        [
            _headline(f"Seed groups ({total})", icon="🌱"),
            _bullet("Open any group card below or use /seed <seed_group_id>.", icon="➡"),
        ]
    )


def format_seed_group_card(group: dict[str, Any]) -> str:
    group_id = group.get("id", "unknown")
    return "\n".join(
        [
            _headline(group.get("name", "Unnamed group"), icon="🌱"),
            _field("ID", group_id, icon="🆔"),
            _field(
                "Seeds",
                (
                    f"{group.get('seed_count', 0)} | unresolved {group.get('unresolved_count', 0)}, "
                    f"resolved {group.get('resolved_count', 0)}, failed {group.get('failed_count', 0)}"
                ),
            ),
            _bullet(f"Open: /seed {group_id}", icon="➡"),
        ]
    )


def format_seed_group(data: dict[str, Any]) -> str:
    group = data.get("group") or {}
    group_id = group.get("id", "unknown")
    return "\n".join(
        [
            _headline(group.get("name", "Unnamed group"), icon="🌱"),
            _field("ID", group_id, icon="🆔"),
            _field(
                "Seeds",
                (
                    f"{group.get('seed_count', 0)} | unresolved {group.get('unresolved_count', 0)}, "
                    f"resolved {group.get('resolved_count', 0)}, failed {group.get('failed_count', 0)}"
                ),
            ),
            *_action_block(
                [
                    f"Channels: /channels {group_id}",
                    f"Candidates: /candidates {group_id}",
                    f"Resolve: /resolveseeds {group_id}",
                ]
            ),
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
        return _headline(f"No imported seed channels{target}.", icon="📭")

    page = items[offset : offset + page_size]
    heading = "Seed channels"
    if group_name:
        heading = f"{heading} | {group_name}"
    lines = [_headline(f"{heading} ({offset + 1}-{offset + len(page)} of {total})", icon="📡")]
    for item in page:
        label = item.get("title") or item.get("username") or item.get("raw_value", "seed")
        lines.extend(
            [
                "",
                _headline(str(label), icon="•"),
                _field("Status", item.get("status", "unknown"), icon=_status_icon(item.get("status"))),
            ]
        )
        if item.get("telegram_url"):
            lines.append(_field("Link", item["telegram_url"], icon="🔗"))
        if item.get("community_id"):
            lines.append(_field("Community", f"/community {item['community_id']}", icon="🏘"))
    return "\n".join(lines)


def format_seed_group_resolution(data: dict[str, Any]) -> str:
    job = data.get("job") or {}
    job_id = job.get("id", "unknown")
    return "\n".join(
        [
            _headline(
                "Seed group resolution queued. Resolved communities will queue initial snapshots.",
                icon="⏳",
            ),
            _field("Job", f"{job_id} ({job.get('type', 'seed.resolve')})"),
            _field("Status", job.get("status", "queued"), icon=_status_icon(job.get("status"))),
            *_action_block([f"Check it with /job {job_id}"]),
        ]
    )


def format_telegram_entity_submission(data: dict[str, Any]) -> str:
    intake = data.get("intake") or {}
    job = data.get("job") or {}
    job_id = job.get("id", "unknown")
    intake_id = intake.get("id", "unknown")
    return "\n".join(
        [
            _headline("Telegram entity classification queued.", icon="📨"),
            _field("Submitted", intake.get("telegram_url") or intake.get("raw_value", "unknown")),
            _field("Intake ID", intake_id, icon="🆔"),
            _field("Job", f"{job_id} ({job.get('type', 'telegram_entity.resolve')})"),
            *_action_block([f"Check it with /job {job_id}", f"Result: /entity {intake_id}"]),
        ]
    )


def format_telegram_entity_intake(data: dict[str, Any]) -> str:
    entity_type = data.get("entity_type") or "pending"
    lines = [
        _headline("Telegram entity intake", icon="🔎"),
        _field("ID", data.get("id", "unknown"), icon="🆔"),
        _field("Submitted", data.get("telegram_url") or data.get("raw_value", "unknown")),
        _field("Status", data.get("status", "unknown"), icon=_status_icon(data.get("status"))),
        _field("Type", entity_type),
    ]
    if data.get("community_id"):
        lines.append(_field("Community", f"/community {data['community_id']}", icon="🏘"))
    if data.get("user_id"):
        lines.append(_field("User row ID", data["user_id"], icon="🆔"))
    if data.get("error_message"):
        lines.append(_field("Error", _shorten(str(data["error_message"]), 240), icon="⛔"))
    return "\n".join(lines)


def format_snapshot_job(data: dict[str, Any], *, community_title: str | None = None) -> str:
    job = data.get("job") or {}
    label = community_title or "Community snapshot"
    job_id = job.get("id", "unknown")
    return "\n".join(
        [
            _headline(label, icon="📸"),
            _field("Snapshot job", f"{job_id} ({job.get('type', 'community.snapshot')})"),
            _field("Status", job.get("status", "queued"), icon=_status_icon(job.get("status"))),
            *_action_block([f"Check it with /job {job_id}"]),
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
        return _headline(f"No snapshotted visible members for {label} yet.", icon="📭")

    lines = [_headline(f"Visible members | {label} ({offset + 1}-{offset + len(items)} of {total})", icon="👥")]
    for index, member in enumerate(items, start=offset + 1):
        name = member.get("username") or member.get("first_name") or str(member.get("tg_user_id", "unknown"))
        lines.extend(
            [
                "",
                _headline(f"{index}. {name}", icon="•"),
                _field("Telegram user ID", member.get("tg_user_id", "unknown")),
                _field("Membership", member.get("membership_status", "member")),
                _field("Activity", member.get("activity_status", "unknown")),
            ]
        )
        if member.get("username"):
            lines.append(_field("Public username", f"@{member['username']}"))
        if member.get("first_seen_at"):
            lines.append(_field("First seen", member["first_seen_at"]))
        if member.get("last_active_at"):
            lines.append(_field("Last active", member["last_active_at"]))
    return "\n".join(lines)


def format_member_export(data: dict[str, Any], *, community_title: str | None = None) -> str:
    label = community_title or "community"
    total = data.get("total", len(data.get("items") or []))
    return _headline(f"Exported {total} visible members for {label}.", icon="📤")


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
        _headline(title, icon="🏘"),
        _field("Community ID", community.get("id", "unknown"), icon="🆔"),
        _field("Status", community.get("status", "unknown"), icon=_status_icon(community.get("status"))),
    ]
    if community.get("username"):
        lines.append(_field("Link", f"https://t.me/{community['username']}", icon="🔗"))
    if community.get("source"):
        lines.append(_field("Source", community["source"]))
    if community.get("member_count") is not None:
        lines.append(_field("Members", community["member_count"], icon="👥"))
    if community.get("match_reason"):
        lines.append(_field("Reason", _shorten(str(community["match_reason"]), 240), icon="📝"))

    if latest_snapshot:
        lines.extend(
            [
                "",
                _section("Latest snapshot", icon="📸"),
                _field("Snapshotted", latest_snapshot.get("collected_at", "unknown")),
                _field("Member count", latest_snapshot.get("member_count", "unknown")),
                _field("Messages 7d", latest_snapshot.get("message_count_7d", "unknown")),
            ]
        )

    if latest_run:
        lines.extend(
            [
                "",
                _section("Latest snapshot run", icon="🕒"),
                _field("Status", latest_run.get("status", "unknown"), icon=_status_icon(latest_run.get("status"))),
                _field("Analysis", latest_run.get("analysis_status", "unknown")),
                _field("Window", f"{latest_run.get('window_days', 'unknown')} days"),
                _field("Members seen", latest_run.get("members_seen", "unknown")),
                _field("Messages seen", latest_run.get("messages_seen", "unknown")),
            ]
        )

    if latest_analysis:
        lines.extend(
            [
                "",
                _section("Latest analysis", icon="🧠"),
                _field("Analyzed", latest_analysis.get("analyzed_at", "unknown")),
            ]
        )
        if latest_analysis.get("summary"):
            lines.append(_field("Summary", _shorten(str(latest_analysis["summary"]), 240)))
        themes = latest_analysis.get("dominant_themes") or []
        if themes:
            lines.append(_field("Themes", ", ".join(str(theme) for theme in themes[:5])))
        if latest_analysis.get("activity_level"):
            lines.append(_field("Activity", latest_analysis["activity_level"]))
        if latest_analysis.get("centrality"):
            lines.append(_field("Centrality", latest_analysis["centrality"]))
        if latest_analysis.get("relevance_notes"):
            lines.append(_field("Relevance", _shorten(str(latest_analysis["relevance_notes"]), 180)))

    return "\n".join(lines)


def format_api_error(message: str) -> str:
    return _field("API error", message, icon="⛔")


def format_whoami(user_id: int, username: str | None = None) -> str:
    lines = [
        _headline("Telegram identity", icon="🪪"),
        _field("User ID", user_id),
    ]
    if username:
        lines.append(_field("Username", f"@{username}"))
    lines.extend(
        [
            "",
            _bullet(
                "Give this User ID to the operator so it can be added to TELEGRAM_ALLOWED_USER_IDS.",
                icon="➡",
            ),
        ]
    )
    return "\n".join(lines)


def format_access_denied(user_id: int | None, username: str | None = None) -> str:
    lines = [_headline("This bot is restricted.", icon="⛔")]
    if user_id is not None:
        lines.append(_field("Your Telegram user ID", user_id))
    if username:
        lines.append(_field("Username", f"@{username}"))
    if user_id is not None:
        lines.append(_bullet("Ask the operator to add this ID to TELEGRAM_ALLOWED_USER_IDS.", icon="➡"))
    return "\n".join(lines)
