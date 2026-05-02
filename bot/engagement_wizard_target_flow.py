# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

import asyncio
from typing import Any

from .runtime import *

_WIZARD_TARGET_RESOLVE_POLL_ATTEMPTS = 20
_WIZARD_TARGET_RESOLVE_POLL_SECONDS = 1.0
_WIZARD_TARGET_RESOLVED_STATUSES = {"resolved", "approved"}
_WIZARD_TARGET_TERMINAL_FAILURE_STATUSES = {"failed", "rejected", "archived"}


def _target_is_ready_for_engagement(target_data: dict[str, Any]) -> bool:
    status = str(target_data.get("status") or "pending")
    return status in _WIZARD_TARGET_RESOLVED_STATUSES and bool(target_data.get("community_id"))


def _target_resolution_error(target_data: dict[str, Any]) -> str:
    status = str(target_data.get("status") or "pending")
    last_error = str(target_data.get("last_error") or "").strip()
    if status in _WIZARD_TARGET_TERMINAL_FAILURE_STATUSES:
        if last_error:
            return last_error
        return "That community could not be resolved."
    return "Still resolving that community. Try again in a moment or /cancel_edit."


async def _wait_for_resolved_target(
    client: Any,
    *,
    target_id: str,
    operator_id: int,
    reviewer: str,
) -> dict[str, Any]:
    await client.resolve_engagement_target(
        target_id,
        requested_by=reviewer,
        operator_user_id=operator_id,
    )
    latest: dict[str, Any] = {}
    for attempt in range(_WIZARD_TARGET_RESOLVE_POLL_ATTEMPTS):
        latest = await client.get_engagement_target(target_id)
        if _target_is_ready_for_engagement(latest):
            return latest
        if str(latest.get("status") or "pending") in _WIZARD_TARGET_TERMINAL_FAILURE_STATUSES:
            return latest
        if attempt + 1 < _WIZARD_TARGET_RESOLVE_POLL_ATTEMPTS:
            await asyncio.sleep(_WIZARD_TARGET_RESOLVE_POLL_SECONDS)
    return latest


async def prepare_wizard_target_state(
    update: Any,
    context: Any,
    *,
    operator_id: int,
    raw_ref: str,
) -> tuple[dict[str, Any] | None, str | None]:
    client = _api_client(context)
    reviewer = _reviewer_label(update)

    try:
        target_data = await client.create_engagement_target(
            target_ref=raw_ref,
            added_by=reviewer,
            operator_user_id=operator_id,
        )
    except BotApiError as exc:
        return None, f"Couldn't add that community: {exc.message}\n\nTry again or cancel setup."

    target_id = str(target_data.get("id") or "")
    target_status = str(target_data.get("status") or "pending")
    target_ref_saved = str(target_data.get("submitted_ref") or raw_ref)

    if target_status == "approved":
        return (
            None,
            f"✅ {target_ref_saved} is already active in the engagement system. Return to Engagements to open it.",
        )

    if not _target_is_ready_for_engagement(target_data):
        try:
            target_data = await _wait_for_resolved_target(
                client,
                target_id=target_id,
                operator_id=operator_id,
                reviewer=reviewer,
            )
        except BotApiError as exc:
            return (
                None,
                f"Couldn't resolve that community: {exc.message}\n\nTry again or cancel setup.",
            )
        if not _target_is_ready_for_engagement(target_data):
            return (
                None,
                "Couldn't resolve that community: "
                + _target_resolution_error(target_data)
                + "\n\nTry again or cancel setup.",
            )

    try:
        eng_data = await client.create_engagement(
            target_id=target_id,
            created_by=reviewer,
        )
    except BotApiError as exc:
        return None, f"Couldn't create engagement: {exc.message}\n\nTry again or cancel setup."

    engagement = eng_data.get("engagement") or eng_data
    engagement_id = str(engagement.get("id") or "")
    return (
        {
            "engagement_id": engagement_id,
            "target_id": target_id,
            "community_id": str(engagement.get("community_id") or target_data.get("community_id") or ""),
            "target_ref": target_ref_saved,
            "topic_id": None,
            "account_id": None,
            "mode": None,
            "join_status": None,
            "join_message": None,
            "join_job_id": None,
            "return_callback": None,
        },
        None,
    )


__all__ = ["prepare_wizard_target_state"]

