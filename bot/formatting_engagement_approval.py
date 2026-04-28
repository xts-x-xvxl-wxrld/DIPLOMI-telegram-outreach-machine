from __future__ import annotations

from typing import Any


def format_approval_queue_header(data: dict[str, Any], *, scoped: bool = False, offset: int = 0) -> str:
    queue_count = int(data.get("queue_count") or 0)
    updating_count = int(data.get("updating_count") or 0)
    empty_state = str(data.get("empty_state") or "")

    if queue_count == 0 and updating_count == 0:
        return "No drafts for approval"

    # All items are placeholders (updating)
    real_items = queue_count - updating_count
    if real_items <= 0 and updating_count > 0:
        return f"Approval queue\nWaiting for updated drafts ({updating_count} updating)"

    scope_label = "Scoped approval queue" if scoped else "Approval queue"
    total = queue_count
    lines = [f"{scope_label} ({total} pending)"]
    if updating_count > 0:
        lines.append(f"{updating_count} draft(s) updating in background")
    if empty_state and queue_count == 0:
        lines.append(empty_state)
    return "\n".join(lines)


def format_draft_card(data: dict[str, Any], *, index: int | None = None) -> str:
    draft_id = str(data.get("draft_id") or "unknown")
    engagement_id = str(data.get("engagement_id") or "unknown")
    target_label = str(data.get("target_label") or "Unknown target")
    text = str(data.get("text") or "No draft text")
    why = str(data.get("why") or "No context provided")
    badge = data.get("badge")

    heading = f"{index}. {target_label}" if index is not None else target_label
    lines = [heading]
    if badge:
        lines.append(f"Status: {badge}")
    lines.extend([
        f"Draft ID: {draft_id}",
        f"Engagement ID: {engagement_id}",
        "",
        "Proposed message",
        _shorten(text, 800),
        "",
        "Why this draft exists",
        _shorten(why, 400),
    ])
    return "\n".join(lines)


def format_approval_result(result: dict[str, Any], *, draft_id: str, action: str) -> str:
    status = str(result.get("result") or "unknown")
    message = str(result.get("message") or "")
    lines = [f"Draft {action}: {status}"]
    if message:
        lines.append(message)
    lines.append(f"Draft ID: {draft_id}")
    return "\n".join(lines)


def format_approve_confirm(draft_id: str, draft_data: dict[str, Any]) -> str:
    target_label = str(draft_data.get("target_label") or "Unknown target")
    text = str(draft_data.get("text") or "")
    lines = [
        f"Approve draft for {target_label}?",
        "",
        "Message to approve:",
        _shorten(text, 400),
        "",
        f"Draft ID: {draft_id}",
        "Tap Confirm to approve and send.",
    ]
    return "\n".join(lines)


def format_reject_confirm(draft_id: str, draft_data: dict[str, Any]) -> str:
    target_label = str(draft_data.get("target_label") or "Unknown target")
    text = str(draft_data.get("text") or "")
    lines = [
        f"Reject draft for {target_label}?",
        "",
        "Message to reject:",
        _shorten(text, 400),
        "",
        f"Draft ID: {draft_id}",
        "Tap Confirm to reject this draft.",
    ]
    return "\n".join(lines)


def format_edit_request_prompt(draft_id: str, draft_data: dict[str, Any]) -> str:
    target_label = str(draft_data.get("target_label") or "Unknown target")
    text = str(draft_data.get("text") or "")
    lines = [
        f"Request edit for draft: {target_label}",
        "",
        "Current draft text:",
        _shorten(text, 400),
        "",
        f"Draft ID: {draft_id}",
        "",
        "Send your edit request as the next message.",
        "The AI will regenerate the draft based on your feedback.",
        "Use /cancel_edit to return to the draft without editing.",
    ]
    return "\n".join(lines)


def format_edit_submitted(draft_id: str, result: dict[str, Any]) -> str:
    status = str(result.get("result") or "queued_update")
    message = str(result.get("message") or "")
    lines = [f"Edit request submitted: {status}"]
    if message:
        lines.append(message)
    lines.append(f"Draft ID: {draft_id}")
    return "\n".join(lines)


def format_approval_queue_empty(*, scoped: bool = False) -> str:
    if scoped:
        return "No drafts pending approval for this engagement."
    return "No drafts for approval"


def format_approval_placeholder_only() -> str:
    return "Approval queue\nWaiting for updated drafts"


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
