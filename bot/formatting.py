from __future__ import annotations

from typing import Any


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
            "/collect <community_id>",
            "/members <community_id>",
            "/exportmembers <community_id>",
            "/engagement_candidates",
            "/approve_reply <candidate_id>",
            "/reject_reply <candidate_id>",
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
                f"Collection job: {job.get('id', 'unknown')} "
                f"({job.get('type', 'collection.run')})",
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
            "Seed group resolution queued. Resolved communities will queue initial collection.",
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


def format_collection_job(data: dict[str, Any], *, community_title: str | None = None) -> str:
    job = data.get("job") or {}
    label = community_title or "Community collection"
    job_id = job.get("id", "unknown")
    return "\n".join(
        [
            f"{label}",
            f"Collection job: {job_id} ({job.get('type', 'collection.run')})",
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
        return f"No collected visible members for {label} yet."

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


def format_engagement_candidates(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "No engagement replies need review right now."

    return f"Engagement replies needing review ({offset + 1}-{offset + len(items)} of {total})"


def format_engagement_candidate_card(item: dict[str, Any], *, index: int | None = None) -> str:
    title = item.get("community_title") or "Community"
    topic = item.get("topic_name") or "Topic"
    candidate_id = item.get("id", "unknown")
    source = _shorten(str(item.get("source_excerpt") or "No source excerpt recorded."), 500)
    reason = _shorten(str(item.get("detected_reason") or "No reason recorded."), 260)
    reply = str(item.get("suggested_reply") or item.get("final_reply") or "No draft reply recorded.")

    heading = f"{index}. {title}" if index is not None else title
    lines = [
        heading,
        f"Topic: {topic}",
        f"Status: {item.get('status', 'unknown')}",
        "",
        f"Source: {source}",
        f"Reason: {reason}",
        "",
        f"Suggested reply: {_shorten(reply, 800)}",
    ]
    risk_notes = item.get("risk_notes") or []
    if risk_notes:
        lines.append(f"Risk notes: {_shorten('; '.join(str(note) for note in risk_notes), 260)}")
    lines.extend(
        [
            "",
            f"Candidate ID: {candidate_id}",
            f"Approve: /approve_reply {candidate_id}",
            f"Reject: /reject_reply {candidate_id}",
        ]
    )
    return "\n".join(lines)


def format_engagement_candidate_review(action: str, item: dict[str, Any]) -> str:
    title = item.get("community_title") or "Community"
    candidate_id = item.get("id", "unknown")
    return "\n".join(
        [
            title,
            f"Candidate ID: {candidate_id}",
            f"Decision: {action}",
            f"Status: {item.get('status', 'unknown')}",
            f"Reviewed by: {item.get('reviewed_by') or 'operator'}",
        ]
    )


def format_community_detail(
    detail: dict[str, Any],
    collection_runs: dict[str, Any] | None = None,
) -> str:
    community = detail.get("community") or {}
    latest_snapshot = detail.get("latest_snapshot") or {}
    latest_analysis = detail.get("latest_analysis") or {}
    latest_run = ((collection_runs or {}).get("items") or [None])[0] or {}
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
                f"Collected: {latest_snapshot.get('collected_at', 'unknown')}",
                f"Member count: {latest_snapshot.get('member_count', 'unknown')}",
                f"Messages 7d: {latest_snapshot.get('message_count_7d', 'unknown')}",
            ]
        )

    if latest_run:
        lines.extend(
            [
                "",
                "Latest collection run",
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
