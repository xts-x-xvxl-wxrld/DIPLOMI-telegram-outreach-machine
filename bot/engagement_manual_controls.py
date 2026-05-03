# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

import re
from typing import Any

from bot.api_client import BotApiClient, BotApiError
from bot.formatting import (
    format_engagement_action_card,
    format_engagement_actions,
    format_engagement_account_assignment_confirmation,
    format_engagement_job_response,
    format_engagement_settings,
)
from bot.ui import (
    engagement_account_confirm_markup,
    engagement_action_pager_markup,
    engagement_job_markup,
)

from .runtime import *


async def _send_engagement_settings(update: Any, context: Any, community_id: str) -> None:
    client = _api_client(context)
    data = await client.get_engagement_settings(community_id)
    await _reply_with_engagement_settings(update, context, community_id, data)


async def _apply_engagement_preset(
    update: Any,
    context: Any,
    community_id: str,
    *,
    preset: str,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    data = await client.update_engagement_settings(
        community_id,
        **_engagement_preset_payload(preset),
        operator_user_id=_telegram_user_id(update),
    )
    await _reply_with_engagement_settings(
        update,
        context,
        community_id,
        data,
        edit_callback=edit_callback,
    )


async def _toggle_engagement_setting(
    update: Any,
    context: Any,
    community_id: str,
    *,
    field: str,
    value: bool,
    edit_callback: bool = False,
) -> None:
    await _update_engagement_settings_from_current(
        update,
        context,
        community_id,
        edit_callback=edit_callback,
        **{field: value},
    )


async def _update_engagement_settings_from_current(
    update: Any,
    context: Any,
    community_id: str,
    *,
    edit_callback: bool = False,
    **updates: Any,
) -> None:
    client = _api_client(context)
    current = await client.get_engagement_settings(community_id)
    payload = _engagement_settings_payload_from_current(current, **updates)
    data = await client.update_engagement_settings(
        community_id,
        **payload,
        operator_user_id=_telegram_user_id(update),
    )
    await _reply_with_engagement_settings(
        update,
        context,
        community_id,
        data,
        edit_callback=edit_callback,
    )


async def _confirm_engagement_account_assignment(
    update: Any,
    context: Any,
    community_id: str,
    *,
    assigned_account_id: str | None,
    edit_callback: bool = False,
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return

    client = _api_client(context)
    current = await client.get_engagement_settings(community_id)
    current_account_id = current.get("assigned_account_id")
    before_label = await _format_account_assignment_label(
        client,
        str(current_account_id) if current_account_id else None,
    )
    after_label = await _format_account_assignment_label(client, assigned_account_id)
    _account_confirm_store(context)[operator_id] = {
        "community_id": community_id,
        "assigned_account_id": assigned_account_id,
    }
    message = format_engagement_account_assignment_confirmation(
        current,
        before_account_label=before_label,
        after_account_label=after_label,
    )
    if edit_callback:
        await _edit_callback_message(
            update,
            message,
            reply_markup=engagement_account_confirm_markup(),
        )
        return
    await _reply(update, message, reply_markup=engagement_account_confirm_markup())


async def _apply_confirmed_engagement_account_assignment(
    update: Any,
    context: Any,
    *,
    edit_callback: bool = False,
) -> None:
    operator_id = _telegram_user_id(update)
    pending = (
        _account_confirm_store(context).pop(operator_id, None)
        if operator_id is not None
        else None
    )
    if not pending:
        await _callback_reply(update, "No pending engagement account change to confirm.")
        return
    await _update_engagement_settings_from_current(
        update,
        context,
        str(pending["community_id"]),
        assigned_account_id=pending.get("assigned_account_id"),
        edit_callback=edit_callback,
    )


async def _cancel_engagement_account_assignment(
    update: Any,
    context: Any,
    *,
    edit_callback: bool = False,
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is not None:
        _account_confirm_store(context).pop(operator_id, None)
    message = "Cancelled engagement account assignment change."
    if edit_callback:
        await _edit_callback_message(update, message)
        return
    await _reply(update, message)


async def _reply_with_engagement_settings(
    update: Any,
    context: Any,
    community_id: str,
    data: dict[str, Any],
    *,
    edit_callback: bool = False,
) -> None:
    message = await _format_engagement_settings_message(context, data)
    reply_markup = _engagement_settings_markup(
        community_id,
        data,
        can_manage=await _is_engagement_admin_async(update, context),
    )
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _callback_reply(update, message, reply_markup=reply_markup)


async def _format_engagement_settings_message(context: Any, data: dict[str, Any]) -> str:
    assigned_account_label: str | None = None
    assigned_account_id = data.get("assigned_account_id")
    if assigned_account_id:
        assigned_account_label = await _lookup_masked_account_label(
            _api_client(context),
            str(assigned_account_id),
        )
    return format_engagement_settings(data, assigned_account_label=assigned_account_label)


async def _format_account_assignment_label(
    client: BotApiClient,
    account_id: str | None,
) -> str:
    if not account_id:
        return "none"
    return await _lookup_masked_account_label(client, account_id) or account_id


async def _lookup_masked_account_label(client: BotApiClient, account_id: str) -> str | None:
    try:
        accounts = await client.get_accounts()
    except BotApiError:
        return None

    for item in accounts.get("items") or []:
        if str(item.get("id") or "") != account_id:
            continue
        phone = str(item.get("phone") or "").strip()
        if phone:
            return f"{account_id} | {_safe_masked_phone(phone)}"
        status = str(item.get("status") or "").strip()
        if status:
            return f"{account_id} | {status}"
        return account_id
    return account_id


def _safe_masked_phone(value: str) -> str:
    if "*" in value:
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) < 7:
        return value
    prefix = "+" if value.strip().startswith("+") else ""
    return f"{prefix}{digits[:3]}*****{digits[-2:]}"


async def _start_engagement_join(update: Any, context: Any, community_id: str) -> None:
    client = _api_client(context)
    data = await client.start_community_join(community_id, requested_by=_reviewer_label(update))
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_engagement_job_response(data, label="Community join", community_id=community_id),
        reply_markup=engagement_job_markup(job_id, community_id=community_id),
    )


async def _start_engagement_detection(
    update: Any,
    context: Any,
    community_id: str,
    *,
    window_minutes: int,
) -> None:
    client = _api_client(context)
    data = await client.start_engagement_detection(
        community_id,
        window_minutes=window_minutes,
        requested_by=_reviewer_label(update),
    )
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_engagement_job_response(
            data,
            label="Engagement detection",
            community_id=community_id,
        ),
        reply_markup=engagement_job_markup(job_id, community_id=community_id),
    )


async def _send_engagement_actions(
    update: Any,
    context: Any,
    *,
    community_id: str | None,
    offset: int,
) -> None:
    client = _api_client(context)
    data = await client.list_engagement_actions(
        community_id=community_id,
        limit=ENGAGEMENT_ACTION_PAGE_SIZE,
        offset=offset,
    )
    await _callback_reply(
        update,
        format_engagement_actions(data, offset=offset),
        reply_markup=engagement_action_pager_markup(
            offset=offset,
            total=data.get("total", 0),
            page_size=ENGAGEMENT_ACTION_PAGE_SIZE,
            community_id=community_id,
        ),
    )
    for index, item in enumerate(data.get("items") or [], start=offset + 1):
        await _callback_reply(update, format_engagement_action_card(item, index=index))


__all__ = [
    "_send_engagement_settings",
    "_apply_engagement_preset",
    "_toggle_engagement_setting",
    "_update_engagement_settings_from_current",
    "_confirm_engagement_account_assignment",
    "_apply_confirmed_engagement_account_assignment",
    "_cancel_engagement_account_assignment",
    "_reply_with_engagement_settings",
    "_format_engagement_settings_message",
    "_format_account_assignment_label",
    "_lookup_masked_account_label",
    "_safe_masked_phone",
    "_start_engagement_join",
    "_start_engagement_detection",
    "_send_engagement_actions",
]
