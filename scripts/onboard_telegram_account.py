from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.settings import get_settings  # noqa: E402
from backend.db.enums import AccountPool, AccountStatus  # noqa: E402
from backend.db.models import TelegramAccount  # noqa: E402
from backend.db.session import AsyncSessionLocal  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a local Telethon session and register it in telegram_accounts."
    )
    parser.add_argument("--phone", help="Telegram account phone number, including country code.")
    parser.add_argument(
        "--session-name",
        help="Safe session file name to store under SESSIONS_DIR. Defaults to the phone number.",
    )
    parser.add_argument(
        "--account-pool",
        choices=[AccountPool.SEARCH.value, AccountPool.ENGAGEMENT.value],
        default=AccountPool.SEARCH.value,
        help="Telegram account pool to register. Defaults to search.",
    )
    parser.add_argument("--notes", help="Optional operator notes for this account.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise SystemExit("TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured first.")

    phone = args.phone or input("Telegram account phone (+countrycode...): ").strip()
    if not phone:
        raise SystemExit("Phone number is required.")

    session_file_name = safe_session_file_name(args.session_name or phone)
    session_file_path = session_file_name
    full_session_path = resolve_session_path(settings.sessions_dir, session_file_path)
    full_session_path.parent.mkdir(parents=True, exist_ok=True)

    await create_or_validate_session(
        session_path=full_session_path,
        api_id=int(settings.telegram_api_id),
        api_hash=settings.telegram_api_hash,
        phone=phone,
    )
    async with AsyncSessionLocal() as session:
        account = await upsert_telegram_account(
            session,
            phone=phone,
            session_file_path=session_file_path,
            account_pool=args.account_pool,
            notes=args.notes,
        )
        await session.commit()

    print(
        f"Registered Telegram account {account.phone} with session "
        f"{account.session_file_path} in pool {account.account_pool}."
    )


async def create_or_validate_session(
    *,
    session_path: Path,
    api_id: int,
    api_hash: str,
    phone: str,
) -> None:
    try:
        from telethon import TelegramClient
    except ImportError as exc:
        raise SystemExit("telethon must be installed before onboarding an account.") from exc

    client = TelegramClient(str(session_path), api_id, api_hash)
    try:
        await client.start(phone=phone)
        if not await client.is_user_authorized():
            raise SystemExit("Telegram login did not authorize the session.")
    finally:
        await client.disconnect()


async def upsert_telegram_account(
    session,
    *,
    phone: str,
    session_file_path: str,
    account_pool: str = AccountPool.SEARCH.value,
    notes: str | None = None,
) -> TelegramAccount:
    account = await session.scalar(select(TelegramAccount).where(TelegramAccount.phone == phone))
    values = account_values(session_file_path=session_file_path, account_pool=account_pool, notes=notes)
    if account is None:
        account = TelegramAccount(id=uuid.uuid4(), phone=phone, **values)
        session.add(account)
    else:
        for key, value in values.items():
            setattr(account, key, value)
    await session.flush()
    return account


def account_values(
    *,
    session_file_path: str,
    account_pool: str = AccountPool.SEARCH.value,
    notes: str | None = None,
) -> dict[str, object]:
    if account_pool not in {AccountPool.SEARCH.value, AccountPool.ENGAGEMENT.value}:
        raise ValueError("account_pool must be search or engagement")
    return {
        "session_file_path": session_file_path,
        "account_pool": account_pool,
        "status": AccountStatus.AVAILABLE.value,
        "flood_wait_until": None,
        "lease_owner": None,
        "lease_expires_at": None,
        "last_error": None,
        "notes": notes,
    }


def safe_session_file_name(raw_value: str) -> str:
    raw_name = raw_value.strip()
    if "/" in raw_name or "\\" in raw_name or ".." in Path(raw_name).parts:
        raise ValueError("Session name must not contain path separators")

    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_name).strip("._-")
    if not stem:
        raise ValueError("Session name must contain at least one safe character")
    if not stem.endswith(".session"):
        stem = f"{stem}.session"
    return stem


def resolve_session_path(sessions_dir: str, session_file_path: str) -> Path:
    base = Path(sessions_dir).resolve()
    target = (base / session_file_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("Session path must stay inside SESSIONS_DIR")
    return target


if __name__ == "__main__":
    asyncio.run(main())
