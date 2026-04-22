from __future__ import annotations

from typing import Any

from .formatting_common import (
    _engagement_candidate_next_actions,
    _engagement_candidate_readiness,
    _percent,
    _shorten,
)


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
        return f"No engagement replies with status {status} right now. No reply opportunities in this view."
    return (
        f"Reply opportunities | {status}\n"
        f"Engagement replies | {status} ({offset + 1}-{offset + len(items)} of {total})"
    )


def format_engagement_candidate_card(item: dict[str, Any], *, index: int | None = None) -> str:
    title = item.get("community_title") or "Community"
    topic = item.get("topic_name") or "Topic"
    candidate_id = item.get("id", "unknown")
    status = str(item.get("status", "unknown"))
    source = _shorten(str(item.get("source_excerpt") or "No source excerpt recorded."), 500)
    reason = _shorten(str(item.get("detected_reason") or "No reason recorded."), 260)
    suggested = str(item.get("suggested_reply") or "No draft reply recorded.")
    final = item.get("final_reply")
    lines = [
        f"{index}. {title}" if index is not None else title,
        f"Readiness: {_engagement_candidate_readiness(item)}",
        f"Topic: {topic}",
        f"Status: {status}",
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
    lines.extend(["", f"Source: {source}", f"Reason: {reason}", "", f"Suggested reply: {_shorten(suggested, 800)}"])
    if final and final != suggested:
        lines.append(f"Final reply: {_shorten(str(final), 800)}")
    prompt_summary = item.get("prompt_render_summary") or {}
    if item.get("prompt_profile_version_id"):
        lines.append(f"Prompt: {prompt_summary.get('profile_name', 'profile')}#{prompt_summary.get('version_number', '?')}")
    risk_notes = item.get("risk_notes") or []
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
        return f"No reply revisions for candidate {candidate_id} yet. Reply opportunity ID: {candidate_id}"
    lines = [
        f"Candidate revisions ({total})",
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
