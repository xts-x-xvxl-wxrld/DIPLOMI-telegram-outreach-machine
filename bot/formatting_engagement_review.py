from __future__ import annotations

from typing import Any

from .formatting_common import (
    _engagement_candidate_next_actions,
    _engagement_candidate_readiness,
    _percent,
    _shorten,
)

_QUEUE_LABELS = {
    "needs_review": "Pending approvals",
    "approved": "Ready to send",
    "failed": "Needs attention",
    "expired": "Expired opportunities",
    "sent": "Sent replies",
    "rejected": "Rejected opportunities",
}


def _queue_heading(status: str) -> str:
    return _QUEUE_LABELS.get(status, status.replace("_", " ").title())


def _queue_guidance(status: str) -> str:
    if status == "needs_review":
        return "Review the freshest reply opportunities first, then edit or approve."
    if status == "approved":
        return "These replies are approved. Send the freshest ready item first."
    if status == "failed":
        return "These opportunities hit a delivery or readiness problem. Open one to retry or fix."
    if status == "expired":
        return "These moments are no longer fresh enough to send. Use them for audit and pattern review."
    if status == "sent":
        return "Review recent sends and confirm the outcomes look healthy."
    if status == "rejected":
        return "Review prior declines and audit context without reopening the queue."
    return "Open a reply opportunity to review the context and next safe action."


def _queue_empty_message(status: str) -> str:
    heading = _queue_heading(status)
    if status == "needs_review":
        return f"{heading}\nNo pending approvals right now."
    if status == "approved":
        return f"{heading}\nNo approved replies are waiting to send."
    if status == "failed":
        return f"{heading}\nNo reply opportunities need operator fixes right now."
    if status == "expired":
        return f"{heading}\nNo expired reply opportunities in this view."
    if status == "sent":
        return f"{heading}\nNo sent replies in this view."
    if status == "rejected":
        return f"{heading}\nNo rejected reply opportunities in this view."
    return f"{heading}\nNo reply opportunities in this view."


def _candidate_next_step(status: str, readiness: str) -> str:
    blocked = readiness.casefold().startswith("blocked:")
    if status == "needs_review":
        if blocked:
            return "Inspect the blocker before approving this reply opportunity."
        return "Review the generated suggestion, edit if needed, then approve."
    if status == "approved":
        if blocked:
            return "Fix the blocker, then queue send while the conversation is still fresh."
        return "Queue send while the conversation is still fresh."
    if status == "failed":
        return "Review the failure, retry if the community is ready, or reject."
    if status == "expired":
        return "Keep this for audit context only; do not send."
    if status == "sent":
        return "Use audit history or revisions if you need to inspect what was sent."
    if status == "rejected":
        return "Use the audit trail if you need the decision context."
    return "Open the full workspace before taking action."


def _candidate_action_sequence(status: str) -> str:
    if status == "needs_review":
        return "edit final reply if needed -> approve -> queue send"
    if status == "approved":
        return "edit final reply if needed -> queue send"
    if status == "failed":
        return "inspect failure -> retry or edit -> approve/send again if ready"
    if status == "expired":
        return "audit only"
    if status == "sent":
        return "audit and revisions only"
    if status == "rejected":
        return "audit only"
    return "open the workspace and decide the next safe action"


def _final_reply_text(suggested: str, final: Any) -> str:
    if not final:
        return "Matches the generated suggestion right now."
    final_text = str(final)
    if final_text == suggested:
        return "Matches the generated suggestion right now."
    return _shorten(final_text, 800)


def _blocked_fix_lines(item: dict[str, Any], status: str, readiness: str) -> list[str]:
    community_id = item.get("community_id")
    settings_command = item.get("fix_settings_command") or (
        f"/engagement_settings {community_id}" if community_id else None
    )
    actions_command = item.get("fix_actions_command") or (
        f"/engagement_actions {community_id}" if community_id else None
    )
    join_command = item.get("fix_join_command") or (
        f"/join_community {community_id}" if community_id else None
    )
    readiness_text = readiness.casefold()
    lines: list[str] = []
    if status == "expired" or "reply expired" in readiness_text:
        lines.append("Fix now: none. This reply opportunity is no longer fresh enough to send.")
        if actions_command:
            lines.append(f"Audit trail: {actions_command}")
        return lines
    if "posting permission off" in readiness_text:
        lines.append("Fix now: open community settings and turn reviewed posting back on.")
        if settings_command:
            lines.append(f"Settings: {settings_command}")
        return lines
    if "no joined engagement account" in readiness_text or "not joined" in readiness_text:
        lines.append("Fix now: open community settings, verify the engagement account, then queue a join.")
        if settings_command:
            lines.append(f"Settings: {settings_command}")
        if join_command:
            lines.append(f"Join: {join_command}")
        return lines
    if "rate limit" in readiness_text or "quiet hours" in readiness_text or "account " in readiness_text:
        lines.append("Fix now: review account readiness, quiet hours, and recent send failures before retrying.")
        if settings_command:
            lines.append(f"Settings: {settings_command}")
        if actions_command:
            lines.append(f"Recent actions: {actions_command}")
        return lines
    if status == "failed":
        lines.append("Fix now: inspect the last send attempt and the community settings before retrying.")
        if actions_command:
            lines.append(f"Recent actions: {actions_command}")
        if settings_command:
            lines.append(f"Settings: {settings_command}")
        return lines
    return lines


def format_engagement_actions(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return "No engagement audit actions match this view."
    return f"Engagement audit ({offset + 1}-{offset + len(items)} of {total})"


def format_engagement_action_card(item: dict[str, Any], *, index: int | None = None) -> str:
    title = f"{item.get('action_type', 'action')} | {item.get('status', 'unknown')}"
    heading = f"{index}. {title}" if index is not None else title
    lines = [heading, f"Action ID: {item.get('id', 'unknown')}", f"Community ID: {item.get('community_id', 'unknown')}"]
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
            f"{band.get('label', 'band')}: {total} | approved {band.get('approved', 0)}, "
            f"rejected {band.get('rejected', 0)}, pending {band.get('pending', 0)}, "
            f"expired {band.get('expired', 0)} | approval {_percent(band.get('approval_rate'))}"
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
        return _queue_empty_message(status)
    heading = _queue_heading(status)
    return "\n".join(
        [
            f"{heading} ({offset + 1}-{offset + len(items)} of {total})",
            _queue_guidance(status),
        ]
    )


def format_engagement_candidate_card(
    item: dict[str, Any],
    *,
    index: int | None = None,
    detail: bool = False,
) -> str:
    title = item.get("community_title") or "Community"
    topic = item.get("topic_name") or "Topic"
    candidate_id = item.get("id", "unknown")
    status = str(item.get("status", "unknown"))
    readiness = _engagement_candidate_readiness(item)
    source = _shorten(str(item.get("source_excerpt") or "No source excerpt recorded."), 500)
    reason = _shorten(str(item.get("detected_reason") or "No reason recorded."), 260)
    suggested = str(item.get("suggested_reply") or "No draft reply recorded.")
    final = item.get("final_reply")
    lines = [
        f"{index}. {title}" if index is not None else title,
        f"Queue: {_queue_heading(status)}",
        f"Readiness: {readiness}",
        f"What to do next: {_candidate_next_step(status, readiness)}",
        f"Topic: {topic}",
        f"Review state: {status}",
    ]
    if item.get("timeliness"):
        freshness_line = f"Freshness: {item['timeliness']}"
        if item.get("moment_strength"):
            freshness_line = f"{freshness_line} | moment {item['moment_strength']}"
        if item.get("reply_value"):
            freshness_line = f"{freshness_line} | value {item['reply_value']}"
        lines.append(freshness_line)
    if item.get("review_deadline_at") or item.get("reply_deadline_at"):
        lines.append(
            "Deadlines: "
            f"review {_shorten(str(item.get('review_deadline_at') or '-'), 60)} | "
            f"reply {_shorten(str(item.get('reply_deadline_at') or '-'), 60)}"
        )
    prompt_summary = item.get("prompt_render_summary") or {}
    risk_notes = item.get("risk_notes") or []
    if detail:
        lines.extend(
            [
                f"Action sequence: {_candidate_action_sequence(status)}",
                "",
                "Source context",
                f"Why this reply opportunity exists: {reason}",
                f"Source: {source}",
                "",
                "Reply workspace",
                f"Generated suggestion: {_shorten(suggested, 800)}",
                f"Final reply: {_final_reply_text(suggested, final)}",
            ]
        )
        if not str(final or "").strip():
            lines.append(
                "Learning shortcuts unlock after you edit Final reply, so saved examples and style "
                "rules reflect a deliberate operator revision."
            )
        fix_lines = _blocked_fix_lines(item, status, readiness)
        if fix_lines:
            lines.extend(["", "Blocked path", *fix_lines])
        if item.get("prompt_profile_version_id"):
            lines.append(
                "Generated by: "
                f"{prompt_summary.get('profile_name', 'profile')}#{prompt_summary.get('version_number', '?')}"
            )
        if risk_notes:
            lines.append(f"Risk notes: {_shorten('; '.join(str(note) for note in risk_notes), 260)}")
        lines.extend(
            [
                "",
                "Audit fields",
                f"Reply opportunity ID: {candidate_id}",
                f"Candidate ID: {candidate_id}",
            ]
        )
        lines.extend(["", "Next safe actions", *_engagement_candidate_next_actions(candidate_id, status)])
    else:
        lines.extend(
            [
                "",
                f"Why this reply opportunity exists: {reason}",
                f"Source: {source}",
                "",
                f"Generated suggestion: {_shorten(suggested, 800)}",
            ]
        )
        if final and final != suggested:
            lines.append(f"Final reply: {_shorten(str(final), 800)}")
        if item.get("prompt_profile_version_id"):
            lines.append(
                f"Prompt: {prompt_summary.get('profile_name', 'profile')}#{prompt_summary.get('version_number', '?')}"
            )
        if risk_notes:
            lines.append(f"Risk notes: {_shorten('; '.join(str(note) for note in risk_notes), 260)}")
        lines.extend(["", f"Reply opportunity ID: {candidate_id}", f"Candidate ID: {candidate_id}"])
        lines.extend(_engagement_candidate_next_actions(candidate_id, status))
    return "\n".join(lines)


def format_engagement_candidate_review(action: str, item: dict[str, Any]) -> str:
    candidate_id = item.get("id", "unknown")
    lines = [
        item.get("community_title") or "Community",
        f"Reply opportunity ID: {candidate_id}",
        f"Candidate ID: {candidate_id}",
        f"Review decision: {action}",
        f"Reply state: {item.get('status', 'unknown')}",
        f"Reviewed by: {item.get('reviewed_by') or 'operator'}",
    ]
    if item.get("status") == "approved":
        lines.append(f"Ready to send: /send_reply {candidate_id}")
    return "\n".join(lines)


def format_engagement_candidate_revisions(data: dict[str, Any], *, candidate_id: str) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return (
            "No saved final-reply revisions for this reply opportunity yet. "
            f"Reply opportunity ID: {candidate_id}"
        )
    lines = [
        f"Reply revisions ({total})",
        f"Reply opportunity ID: {candidate_id}",
        f"Candidate ID: {candidate_id}",
    ]
    for item in items[:10]:
        lines.extend(["", f"Revision {item.get('revision_number', '?')}", f"Edited by: {item.get('edited_by') or 'operator'}"])
        if item.get("edit_reason"):
            lines.append(f"Reason: {_shorten(str(item['edit_reason']), 160)}")
        if item.get("created_at"):
            lines.append(f"Created: {item['created_at']}")
        lines.append(f"Reply: {_shorten(str(item.get('reply_text') or ''), 800)}")
    if len(items) > 10:
        lines.append(f"...and {len(items) - 10} more")
    return "\n".join(lines)
