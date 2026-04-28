from __future__ import annotations

from typing import Any

from .api_client import BotApiError


def wizard_account_status_note(state: dict[str, Any]) -> str | None:
    join_status = str(state.get("join_status") or "").strip()
    join_message = str(state.get("join_message") or "").strip()
    if join_message:
        return join_message
    if join_status == "joined":
        return "Account status: joined and ready for replies."
    if join_status == "connecting":
        return "Account status: connecting now. The join was queued and replies will start after it finishes."
    if join_status == "failed":
        return "Account status: couldn't join yet. Pick another account or retry this step."
    return None


def _extract_job_ref(payload: dict[str, Any]) -> dict[str, Any]:
    job = payload.get("job")
    if isinstance(job, dict):
        return job
    return payload


async def inspect_join_progress(
    client: Any,
    *,
    community_id: str,
    account_id: str,
    job_payload: dict[str, Any],
) -> tuple[str, str, str | None]:
    job = _extract_job_ref(job_payload)
    job_id = str(job.get("id") or "") or None
    connecting_message = (
        "Account status: connecting now. The join was queued and replies will start after it finishes."
    )
    job_status = str(job.get("status") or "").strip().lower()
    if job_status == "failed":
        return (
            "failed",
            "Account status: the join queue failed before the account could connect. Pick another account or retry this step.",
            job_id,
        )

    try:
        action_data = await client.list_engagement_actions(
            community_id=community_id,
            action_type="join",
            limit=10,
        )
    except BotApiError:
        return "connecting", connecting_message, job_id

    for item in action_data.get("items") or []:
        if str(item.get("telegram_account_id") or "") != account_id:
            continue
        action_status = str(item.get("status") or "").strip().lower()
        error_message = str(item.get("error_message") or "").strip()
        if action_status == "sent":
            return "joined", "Account status: joined and ready for replies.", job_id
        if action_status in {"failed", "skipped"}:
            detail = f" {error_message}" if error_message else ""
            return "failed", f"Account status: couldn't join this community yet.{detail}".strip(), job_id
        if action_status == "queued":
            return "connecting", connecting_message, job_id

    return "connecting", connecting_message, job_id


async def start_wizard_account_join(
    client: Any,
    *,
    state: dict[str, Any],
    account_id: str,
    reviewer: str,
) -> bool:
    community_id = str(state.get("community_id") or "").strip()
    join_failed = False
    if community_id:
        try:
            join_job = await client.start_community_join(
                community_id,
                telegram_account_id=account_id,
                requested_by=reviewer,
            )
            join_status, join_message, join_job_id = await inspect_join_progress(
                client,
                community_id=community_id,
                account_id=account_id,
                job_payload=join_job,
            )
        except BotApiError as exc:
            join_status = "failed"
            join_message = f"Account status: couldn't start the community join yet. {exc.message}"
            join_job_id = None
        state["join_status"] = join_status
        state["join_message"] = join_message
        state["join_job_id"] = join_job_id
        join_failed = join_status == "failed"
    else:
        state["join_status"] = "failed"
        state["join_message"] = "Account status: this draft is missing its community link, so the join could not start yet."
        state["join_job_id"] = None
        join_failed = True
    return join_failed


__all__ = ["start_wizard_account_join", "wizard_account_status_note"]
