from __future__ import annotations

from typing import Any


def format_approval_queue_header(data: dict[str, Any], *, scoped: bool = False, offset: int = 0) -> str:
    queue_count = int(data.get("queue_count") or 0)
    updating_count = int(data.get("updating_count") or 0)
    empty_state = str(data.get("empty_state") or "")

    if queue_count == 0 and updating_count == 0:
        return "No drafts waiting for review."

    real_items = queue_count - updating_count
    if real_items <= 0 and updating_count > 0:
        return "\n".join(
            [
                "Approval queue",
                f"Drafts are updating in the background ({updating_count} updating).",
            ]
        )

    scope_label = "Drafts for this engagement" if scoped else "Approval queue"
    lines = [f"{scope_label} ({queue_count} pending)", "Review the draft below."]
    if updating_count > 0:
        lines.append(f"{updating_count} draft(s) still updating in the background.")
    if empty_state and queue_count == 0:
        lines.append(empty_state)
    return "\n".join(lines)


def format_draft_card(data: dict[str, Any], *, index: int | None = None) -> str:
    target_label = str(data.get("target_label") or "Unknown target")
    text = str(data.get("text") or "No draft text")
    why = str(data.get("why") or "No context provided")
    badge = data.get("badge")
    identity_lines = _draft_identity_lines(data)

    heading = f"{index}. {target_label}" if index is not None else target_label
    lines = [heading]
    if badge:
        lines.append(f"Status: {badge}")
    lines.extend(identity_lines)
    lines.extend(
        [
            "",
            "Draft",
            _shorten(text, 800),
            "",
            "Why now",
            _shorten(why, 400),
        ]
    )
    return "\n".join(lines)


def format_approval_result(result: dict[str, Any], *, draft_id: str, action: str) -> str:
    status = str(result.get("result") or "unknown")
    message = str(result.get("message") or "")
    job_id = str(result.get("job_id") or "")
    job_type = str(result.get("job_type") or "")
    lines = [f"Draft {action}: {status}."]
    if message:
        lines.append(message)
    if job_id:
        job_label = f"{job_id} ({job_type})" if job_type else job_id
        lines.append(f"Send job: {job_label}")
    return "\n".join(lines)


def format_approve_confirm(draft_id: str, draft_data: dict[str, Any]) -> str:
    target_label = str(draft_data.get("target_label") or "Unknown target")
    text = str(draft_data.get("text") or "")
    lines = [f"Approve this draft for {target_label}?"]
    lines.extend(_draft_identity_lines(draft_data))
    lines.extend(["", "Draft", _shorten(text, 400), "", "Confirm queues it to send."])
    return "\n".join(lines)


def format_reject_confirm(draft_id: str, draft_data: dict[str, Any]) -> str:
    target_label = str(draft_data.get("target_label") or "Unknown target")
    text = str(draft_data.get("text") or "")
    lines = [f"Reject this draft for {target_label}?"]
    lines.extend(_draft_identity_lines(draft_data))
    lines.extend(["", "Draft", _shorten(text, 400), "", "Confirm removes it from the queue."])
    return "\n".join(lines)


def format_edit_request_prompt(draft_id: str, draft_data: dict[str, Any]) -> str:
    target_label = str(draft_data.get("target_label") or "Unknown target")
    text = str(draft_data.get("text") or "")
    lines = [f"Request changes for {target_label}"]
    lines.extend(_draft_identity_lines(draft_data))
    lines.extend(
        [
            "",
            "Current draft",
            _shorten(text, 400),
            "",
            "Reply with the change you want.",
            "Use /cancel_edit to stop.",
        ]
    )
    return "\n".join(lines)


def format_edit_submitted(draft_id: str, result: dict[str, Any]) -> str:
    status = str(result.get("result") or "queued_update")
    message = str(result.get("message") or "")
    lines = [f"Edit request submitted: {status}."]
    if message:
        lines.append(message)
    return "\n".join(lines)


def format_approval_queue_empty(*, scoped: bool = False) -> str:
    if scoped:
        return "No drafts waiting for review in this engagement."
    return "No drafts waiting for review."


def format_approval_placeholder_only() -> str:
    return "Approval queue\nDrafts are updating in the background."


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _draft_identity_lines(data: dict[str, Any]) -> list[str]:
    engagement_label = str(data.get("engagement_label") or "").strip()
    community_label = str(data.get("community_label") or "").strip()
    lines: list[str] = []
    if engagement_label:
        lines.append(f"Engagement: {engagement_label}")
    if community_label and community_label != engagement_label:
        lines.append(f"Community: {community_label}")
    return lines
