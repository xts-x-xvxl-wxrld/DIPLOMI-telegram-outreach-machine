from __future__ import annotations

from typing import Any

from bot.account_onboarding import (
    safe_session_file_name,
    validate_onboarding_account_pool,
)
from bot.api_client import BotApiError
from bot.formatting import (
    format_account_onboarding_code_sent,
    format_account_onboarding_password_required,
    format_account_onboarding_registered,
    format_account_onboarding_usage,
    format_api_error,
)
from bot.runtime import _api_client, _callback_reply, _reply, _reviewer_label, _telegram_user_id
from bot.ui import accounts_cockpit_markup

ACCOUNT_ONBOARDING_STORE_KEY = "account_onboarding_store"
SKIP_VALUES = {"-", "none", "skip"}


async def add_account_command(update: Any, context: Any) -> None:
    args = [str(arg).strip() for arg in getattr(context, "args", []) if str(arg).strip()]
    if args and args[0].casefold() == "cancel":
        _account_onboarding_store(context).pop(_telegram_user_id(update), None)
        await _delete_incoming_message(update)
        await _reply(update, "Account onboarding cancelled.", reply_markup=accounts_cockpit_markup())
        return

    if len(args) == 1:
        await _delete_incoming_message(update)
        await begin_account_onboarding_flow(update, context, args[0])
        return

    if len(args) < 2:
        await _reply(
            update,
            format_account_onboarding_usage(),
            reply_markup=accounts_cockpit_markup(),
        )
        return

    account_pool, phone = args[0], args[1]
    session_name = args[2] if len(args) >= 3 else None
    notes = " ".join(args[3:]).strip() or None
    await _delete_incoming_message(update)

    try:
        normalized_pool = validate_onboarding_account_pool(account_pool)
        session_file_name = safe_session_file_name(session_name or phone)
    except ValueError as exc:
        await _reply(
            update,
            format_account_onboarding_usage(str(exc)),
            reply_markup=accounts_cockpit_markup(),
        )
        return

    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _reply(update, "Telegram did not include a user ID on this update.")
        return

    client = _api_client(context)
    try:
        response = await client.start_account_onboarding(
            account_pool=normalized_pool,
            phone=phone,
            session_name=session_file_name,
            notes=notes,
            requested_by=_reviewer_label(update),
        )
    except BotApiError as exc:
        await _reply(
            update,
            format_api_error(exc.message),
            reply_markup=accounts_cockpit_markup(),
        )
        return

    _account_onboarding_store(context)[operator_id] = {
        "step": "code",
        "account_pool": normalized_pool,
        "phone": phone,
        "session_file_name": str(response.get("session_file_name") or session_file_name),
        "phone_code_hash": str(response.get("phone_code_hash") or ""),
        "notes": notes,
    }
    await _reply(
        update,
        format_account_onboarding_code_sent(
            account_pool=normalized_pool,
            phone=phone,
            session_file_name=str(response.get("session_file_name") or session_file_name),
        ),
        reply_markup=accounts_cockpit_markup(),
    )


async def begin_account_onboarding_flow(update: Any, context: Any, account_pool: str) -> None:
    try:
        normalized_pool = validate_onboarding_account_pool(account_pool)
    except ValueError as exc:
        await _callback_reply(
            update,
            format_account_onboarding_usage(str(exc)),
            reply_markup=accounts_cockpit_markup(),
        )
        return

    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return

    _account_onboarding_store(context)[operator_id] = {
        "step": "phone",
        "account_pool": normalized_pool,
    }
    await _callback_reply(
        update,
        _format_account_onboarding_prompt(
            normalized_pool,
            "Send the phone number for this Telegram account.",
            example="+36123456789",
        ),
        reply_markup=accounts_cockpit_markup(),
    )


async def handle_account_onboarding_text(update: Any, context: Any) -> bool:
    if update.message is None or update.message.text is None:
        return False

    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return False

    store = _account_onboarding_store(context)
    pending = store.get(operator_id)
    if not pending:
        return False

    secret_text = update.message.text.strip()
    await _delete_incoming_message(update)
    step = str(pending.get("step") or "")
    if step == "phone":
        await _handle_account_onboarding_phone(update, pending, secret_text)
        return True
    if step == "session_name":
        await _handle_account_onboarding_session_name(update, pending, secret_text)
        return True
    if step == "notes":
        await _start_account_onboarding_from_pending(update, context, pending)
        return True

    if not secret_text:
        await _reply(update, "Send the Telegram login code, or /add_account cancel.")
        return True

    client = _api_client(context)
    code = str(pending.get("code") or secret_text)
    password = secret_text if pending.get("step") == "password" else None
    try:
        response = await client.complete_account_onboarding(
            account_pool=str(pending["account_pool"]),
            phone=str(pending["phone"]),
            session_name=str(pending["session_file_name"]),
            phone_code_hash=str(pending["phone_code_hash"]),
            code=code,
            password=password,
            notes=pending.get("notes"),
            requested_by=_reviewer_label(update),
        )
    except BotApiError as exc:
        if "2FA password is required" in exc.message or "password is required" in exc.message:
            pending["step"] = "password"
            pending["code"] = code
            await _reply(
                update,
                format_account_onboarding_password_required(phone=str(pending["phone"])),
                reply_markup=accounts_cockpit_markup(),
            )
            return True
        await _reply(update, format_api_error(exc.message), reply_markup=accounts_cockpit_markup())
        return True

    store.pop(operator_id, None)
    await _reply(
        update,
        format_account_onboarding_registered(
            account_pool=str(response.get("account_pool") or pending["account_pool"]),
            phone=str(response.get("phone") or pending["phone"]),
            session_file_name=str(response.get("session_file_name") or pending["session_file_name"]),
        ),
        reply_markup=accounts_cockpit_markup(),
    )
    return True


async def _handle_account_onboarding_phone(update: Any, pending: dict[str, Any], phone: str) -> None:
    if not phone:
        await _reply(update, "Send the account phone number, or /add_account cancel.")
        return

    pending["phone"] = phone
    pending["step"] = "session_name"
    try:
        default_session_name = safe_session_file_name(phone)
    except ValueError:
        default_session_name = "telegram-account.session"

    await _reply(
        update,
        _format_account_onboarding_prompt(
            str(pending["account_pool"]),
            "Send a session name for this account, or send skip to use the default.",
            example=default_session_name,
        ),
        reply_markup=accounts_cockpit_markup(),
    )


async def _handle_account_onboarding_session_name(
    update: Any,
    pending: dict[str, Any],
    session_name: str,
) -> None:
    raw_session_name = str(pending.get("phone") or "") if _is_skip_value(session_name) else session_name
    try:
        pending["session_file_name"] = safe_session_file_name(raw_session_name)
    except ValueError as exc:
        await _reply(
            update,
            _format_account_onboarding_prompt(
                str(pending["account_pool"]),
                f"{exc}. Send a different session name, or send skip.",
            ),
            reply_markup=accounts_cockpit_markup(),
        )
        return

    pending["step"] = "notes"
    await _reply(
        update,
        _format_account_onboarding_prompt(
            str(pending["account_pool"]),
            "Send notes for this account, or send skip to leave notes empty.",
            example="warm spare",
        ),
        reply_markup=accounts_cockpit_markup(),
    )


async def _start_account_onboarding_from_pending(
    update: Any,
    context: Any,
    pending: dict[str, Any],
) -> None:
    notes = update.message.text.strip() if update.message and update.message.text else ""
    pending["notes"] = None if _is_skip_value(notes) else notes

    client = _api_client(context)
    try:
        response = await client.start_account_onboarding(
            account_pool=str(pending["account_pool"]),
            phone=str(pending["phone"]),
            session_name=str(pending["session_file_name"]),
            notes=pending.get("notes"),
            requested_by=_reviewer_label(update),
        )
    except BotApiError as exc:
        _account_onboarding_store(context).pop(_telegram_user_id(update), None)
        await _reply(
            update,
            format_api_error(exc.message),
            reply_markup=accounts_cockpit_markup(),
        )
        return

    pending.update(
        {
            "step": "code",
            "session_file_name": str(response.get("session_file_name") or pending["session_file_name"]),
            "phone_code_hash": str(response.get("phone_code_hash") or ""),
        }
    )
    await _reply(
        update,
        format_account_onboarding_code_sent(
            account_pool=str(pending["account_pool"]),
            phone=str(pending["phone"]),
            session_file_name=str(pending["session_file_name"]),
        ),
        reply_markup=accounts_cockpit_markup(),
    )


def _account_onboarding_store(context: Any) -> dict[int | None, dict[str, Any]]:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None)
    if not isinstance(bot_data, dict):
        return {}
    store = bot_data.get(ACCOUNT_ONBOARDING_STORE_KEY)
    if not isinstance(store, dict):
        store = {}
        bot_data[ACCOUNT_ONBOARDING_STORE_KEY] = store
    return store


async def _delete_incoming_message(update: Any) -> None:
    message = getattr(update, "message", None)
    delete = getattr(message, "delete", None)
    if delete is None:
        return
    try:
        await delete()
    except Exception:
        return


def _format_account_onboarding_prompt(account_pool: str, prompt: str, *, example: str | None = None) -> str:
    lines = [
        f"Add {account_pool} Telegram account",
        "",
        prompt,
        "Send /add_account cancel to stop.",
    ]
    if example:
        lines.extend(["", f"Example: {example}"])
    return "\n".join(lines)


def _is_skip_value(value: str) -> bool:
    return value.strip().casefold() in SKIP_VALUES


__all__ = [
    "ACCOUNT_ONBOARDING_STORE_KEY",
    "add_account_command",
    "begin_account_onboarding_flow",
    "handle_account_onboarding_text",
]
