from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import Settings
from backend.services.account_onboarding import (
    resolve_session_path,
    safe_session_file_name,
    upsert_telegram_account,
    validate_onboarding_account_pool,
)


class AccountOnboardingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AccountOnboardingStart:
    account_pool: str
    phone: str
    session_file_name: str
    phone_code_hash: str
    status: str = "code_sent"


@dataclass(frozen=True)
class AccountOnboardingComplete:
    account_pool: str
    phone: str
    session_file_name: str
    status: str


async def start_telegram_account_onboarding(
    *,
    settings: Settings,
    account_pool: str,
    phone: str,
    session_name: str | None = None,
) -> AccountOnboardingStart:
    _require_telegram_api_settings(settings)
    normalized_pool = validate_onboarding_account_pool(account_pool)
    session_file_name = safe_session_file_name(session_name or phone)
    session_path = _prepare_session_path(settings, session_file_name)

    client = _telegram_client(session_path, settings)
    try:
        await client.connect()
        sent_code = await client.send_code_request(phone)
    except ValueError as exc:
        raise AccountOnboardingError("invalid_phone", str(exc)) from exc
    except Exception as exc:
        raise AccountOnboardingError("telegram_start_failed", str(exc)) from exc
    finally:
        await _disconnect_client(client)

    phone_code_hash = getattr(sent_code, "phone_code_hash", None)
    if not phone_code_hash:
        raise AccountOnboardingError(
            "telegram_start_failed",
            "Telegram did not return a login code token.",
        )

    return AccountOnboardingStart(
        account_pool=normalized_pool,
        phone=phone,
        session_file_name=session_file_name,
        phone_code_hash=str(phone_code_hash),
    )


async def complete_telegram_account_onboarding(
    *,
    db: AsyncSession,
    settings: Settings,
    account_pool: str,
    phone: str,
    session_name: str,
    phone_code_hash: str,
    code: str,
    password: str | None = None,
    notes: str | None = None,
) -> AccountOnboardingComplete:
    _require_telegram_api_settings(settings)
    normalized_pool = validate_onboarding_account_pool(account_pool)
    session_file_name = safe_session_file_name(session_name)
    session_path = _prepare_session_path(settings, session_file_name)

    client = _telegram_client(session_path, settings)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await _sign_in(
                client,
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash,
                password=password,
            )
        if not await client.is_user_authorized():
            raise AccountOnboardingError(
                "telegram_auth_failed",
                "Telegram login did not authorize the session.",
            )
    except AccountOnboardingError:
        raise
    except Exception as exc:
        raise AccountOnboardingError("telegram_auth_failed", str(exc)) from exc
    finally:
        await _disconnect_client(client)

    await upsert_telegram_account(
        db,
        phone=phone,
        session_file_path=session_file_name,
        account_pool=normalized_pool,
        notes=notes,
    )
    return AccountOnboardingComplete(
        account_pool=normalized_pool,
        phone=phone,
        session_file_name=session_file_name,
        status="registered",
    )


async def _sign_in(
    client: Any,
    *,
    phone: str,
    code: str,
    phone_code_hash: str,
    password: str | None,
) -> None:
    try:
        from telethon.errors import SessionPasswordNeededError
    except ImportError as exc:
        raise AccountOnboardingError(
            "telethon_not_installed",
            "telethon must be installed before onboarding an account.",
        ) from exc

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError as exc:
        if not password:
            raise AccountOnboardingError(
                "password_required",
                "Telegram 2FA password is required for this account.",
            ) from exc
        await client.sign_in(password=password)


def _require_telegram_api_settings(settings: Settings) -> None:
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise AccountOnboardingError(
            "telegram_api_unconfigured",
            "TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured first.",
        )


def _prepare_session_path(settings: Settings, session_file_name: str) -> Path:
    session_path = resolve_session_path(settings.sessions_dir, session_file_name)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    return session_path


def _telegram_client(session_path: Path, settings: Settings) -> Any:
    try:
        from telethon import TelegramClient
    except ImportError as exc:
        raise AccountOnboardingError(
            "telethon_not_installed",
            "telethon must be installed before onboarding an account.",
        ) from exc
    return TelegramClient(str(session_path), int(settings.telegram_api_id), settings.telegram_api_hash)


async def _disconnect_client(client: Any) -> None:
    disconnect = getattr(client, "disconnect", None)
    if disconnect is not None:
        await disconnect()
