from __future__ import annotations

from typing import Any

from .formatting_common import _percent, _shorten

_QUEUE_LABELS = {
    "needs_review": "Pending approvals",
    "approved": "Ready to send",
    "failed": "Needs attention",
    "expired": "Expired opportunities",
    "sent": "Sent replies",
    "rejected": "Rejected opportunities",
}


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
