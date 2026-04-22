from __future__ import annotations

from typing import Any

def _engagement_candidate_readiness(item: dict[str, Any]) -> str:
    readiness = _backend_readiness_text(item, "readiness", "send_readiness", "readiness_summary")
    if readiness:
        return readiness

    block_reason = _backend_block_reason(item, "send_block_reason", "blocked_reason", "block_reason")
    if block_reason:
        return block_reason

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
    readiness = _backend_readiness_text(
        item,
        "readiness",
        "community_readiness",
        "readiness_summary",
    )
    if readiness:
        return readiness

    block_reason = _backend_block_reason(item, "posting_block_reason", "blocked_reason", "block_reason")
    if block_reason:
        return block_reason

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
    readiness = _backend_readiness_text(
        data,
        "readiness",
        "community_readiness",
        "readiness_summary",
    )
    if readiness:
        return readiness

    block_reason = _backend_block_reason(data, "posting_block_reason", "blocked_reason", "block_reason")
    if block_reason:
        return block_reason
    if data.get("quiet_hours_active") is True:
        return "Blocked: quiet hours active"
    if data.get("rate_limit_active") is True or data.get("rate_limited") is True:
        return "Blocked: rate limit active"
    if data.get("has_joined_engagement_account") is False:
        return "Blocked: no joined engagement account"
    account_status = str(data.get("assigned_account_status") or "").strip().casefold()
    if account_status in {"rate_limited", "banned"}:
        return f"Blocked: account {account_status.replace('_', ' ')}"

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


def _backend_readiness_text(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        raw_value = data.get(key)
        if not raw_value:
            continue
        if isinstance(raw_value, dict):
            for nested_key in ("label", "summary", "message", "reason", "status"):
                nested_value = raw_value.get(nested_key)
                if nested_value:
                    return str(nested_value)
            continue
        return str(raw_value)
    return None


def _backend_block_reason(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        raw_value = data.get(key)
        if not raw_value:
            continue
        text = str(raw_value).strip()
        if not text:
            continue
        if text.casefold().startswith("blocked:"):
            return text
        return f"Blocked: {text}"
    reasons = data.get("readiness_reasons") or data.get("blocked_reasons")
    if isinstance(reasons, list) and reasons:
        first_reason = str(reasons[0]).strip()
        if first_reason:
            if first_reason.casefold().startswith("blocked:"):
                return first_reason
            return f"Blocked: {first_reason}"
    return None


def _target_status_label(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "unknown").replace("_", " ")
    if status == "approved":
        return "approved for engagement"
    if status == "resolved":
        return "resolved, awaiting approval"
    if status == "pending":
        return "waiting for resolution"
    return status


def _settings_mode_label(value: Any) -> str:
    mode = str(value or "disabled")
    labels = {
        "disabled": "paused",
        "observe": "watch only",
        "suggest": "draft replies for review",
        "require_approval": "ready with review",
    }
    return labels.get(mode, mode.replace("_", " "))


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


def _format_time_value(value: Any) -> str:
    if value is None:
        return "?"
    text = str(value).strip()
    if len(text) >= 5 and text[2] == ":":
        return text[:5]
    return text or "?"


def _percent(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "n/a"
