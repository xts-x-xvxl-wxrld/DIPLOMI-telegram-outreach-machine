from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import AccountPool, AccountStatus
from backend.db.models import TelegramAccount

AccountPurpose = Literal[
    "expansion",
    "community_snapshot",
    "collection",
    "entity_intake",
    "engagement_target_resolve",
    "engagement_join",
    "engagement_send",
]
ACCOUNT_PURPOSES: tuple[AccountPurpose, ...] = (
    "expansion",
    "community_snapshot",
    "collection",
    "entity_intake",
    "engagement_target_resolve",
    "engagement_join",
    "engagement_send",
)
PURPOSE_ACCOUNT_POOLS: dict[AccountPurpose, AccountPool] = {
    "expansion": AccountPool.SEARCH,
    "community_snapshot": AccountPool.SEARCH,
    "collection": AccountPool.SEARCH,
    "entity_intake": AccountPool.SEARCH,
    "engagement_target_resolve": AccountPool.SEARCH,
    "engagement_join": AccountPool.ENGAGEMENT,
    "engagement_send": AccountPool.ENGAGEMENT,
}
ReleaseOutcome = Literal["success", "error", "rate_limited", "banned"]


class NoAccountAvailable(RuntimeError):
    pass


@dataclass(frozen=True)
class AccountLease:
    account_id: UUID
    phone: str
    session_file_path: str
    lease_owner: str
    lease_expires_at: datetime


async def acquire_account(
    session: AsyncSession,
    *,
    job_id: str,
    purpose: AccountPurpose,
    lease_seconds: int = 900,
    now: datetime | None = None,
) -> AccountLease:
    validate_account_purpose(purpose)
    required_pool = account_pool_for_purpose(purpose)

    current_time = now or utcnow()
    await recover_stale_leases(session, now=current_time)

    account = await session.scalar(
        select(TelegramAccount)
        .where(
            TelegramAccount.account_pool == required_pool.value,
            or_(
                TelegramAccount.status == AccountStatus.AVAILABLE.value,
                and_(
                    TelegramAccount.status == AccountStatus.RATE_LIMITED.value,
                    TelegramAccount.flood_wait_until <= current_time,
                ),
            )
        )
        .order_by(TelegramAccount.last_used_at.asc().nullsfirst(), TelegramAccount.added_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if account is None:
        raise NoAccountAvailable(f"No Telegram account is available for pool {required_pool.value}")

    lease_expires_at = current_time + timedelta(seconds=lease_seconds)
    account.status = AccountStatus.IN_USE.value
    account.lease_owner = job_id
    account.lease_expires_at = lease_expires_at
    account.last_used_at = current_time
    await session.flush()

    return AccountLease(
        account_id=account.id,
        phone=account.phone,
        session_file_path=account.session_file_path,
        lease_owner=job_id,
        lease_expires_at=lease_expires_at,
    )


async def acquire_account_by_id(
    session: AsyncSession,
    *,
    account_id: UUID,
    job_id: str,
    purpose: AccountPurpose,
    lease_seconds: int = 900,
    now: datetime | None = None,
) -> AccountLease:
    validate_account_purpose(purpose)
    required_pool = account_pool_for_purpose(purpose)

    current_time = now or utcnow()
    await recover_stale_leases(session, now=current_time)

    account = await session.scalar(
        select(TelegramAccount)
        .where(
            TelegramAccount.id == account_id,
            TelegramAccount.account_pool == required_pool.value,
            or_(
                TelegramAccount.status == AccountStatus.AVAILABLE.value,
                and_(
                    TelegramAccount.status == AccountStatus.RATE_LIMITED.value,
                    TelegramAccount.flood_wait_until <= current_time,
                ),
            ),
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if account is None:
        raise NoAccountAvailable(f"Requested Telegram account is not available for pool {required_pool.value}")

    lease_expires_at = current_time + timedelta(seconds=lease_seconds)
    account.status = AccountStatus.IN_USE.value
    account.lease_owner = job_id
    account.lease_expires_at = lease_expires_at
    account.last_used_at = current_time
    await session.flush()

    return AccountLease(
        account_id=account.id,
        phone=account.phone,
        session_file_path=account.session_file_path,
        lease_owner=job_id,
        lease_expires_at=lease_expires_at,
    )


async def release_account(
    session: AsyncSession,
    *,
    account_id: UUID,
    job_id: str,
    outcome: ReleaseOutcome,
    flood_wait_seconds: int | None = None,
    error_message: str | None = None,
    now: datetime | None = None,
) -> None:
    account = await session.scalar(
        select(TelegramAccount)
        .where(TelegramAccount.id == account_id)
        .with_for_update()
        .limit(1)
    )
    if account is None or account.lease_owner != job_id:
        return

    updates = release_updates(
        outcome=outcome,
        flood_wait_seconds=flood_wait_seconds,
        error_message=error_message,
        now=now or utcnow(),
    )
    for key, value in updates.items():
        setattr(account, key, value)
    await session.flush()


async def recover_stale_leases(session: AsyncSession, now: datetime | None = None) -> int:
    current_time = now or utcnow()
    result = await session.execute(
        update(TelegramAccount)
        .where(
            TelegramAccount.status == AccountStatus.IN_USE.value,
            TelegramAccount.lease_expires_at < current_time,
        )
        .values(
            status=AccountStatus.AVAILABLE.value,
            lease_owner=None,
            lease_expires_at=None,
        )
    )
    return result.rowcount or 0


def release_updates(
    *,
    outcome: ReleaseOutcome,
    flood_wait_seconds: int | None = None,
    error_message: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    current_time = now or utcnow()
    base: dict[str, object] = {
        "lease_owner": None,
        "lease_expires_at": None,
        "last_error": error_message,
    }

    if outcome == "success":
        return {
            **base,
            "status": AccountStatus.AVAILABLE.value,
            "last_error": None,
            "flood_wait_until": None,
        }
    if outcome == "error":
        return {**base, "status": AccountStatus.AVAILABLE.value}
    if outcome == "rate_limited":
        if flood_wait_seconds is None:
            raise ValueError("flood_wait_seconds is required for rate_limited outcome")
        return {
            **base,
            "status": AccountStatus.RATE_LIMITED.value,
            "flood_wait_until": current_time + timedelta(seconds=flood_wait_seconds),
        }
    if outcome == "banned":
        return {**base, "status": AccountStatus.BANNED.value}
    raise ValueError(f"Unknown release outcome: {outcome}")


def validate_account_purpose(purpose: str) -> AccountPurpose:
    if purpose not in ACCOUNT_PURPOSES:
        allowed = ", ".join(ACCOUNT_PURPOSES)
        raise ValueError(f"purpose must be one of: {allowed}")
    return cast(AccountPurpose, purpose)


def account_pool_for_purpose(purpose: str) -> AccountPool:
    validated = validate_account_purpose(purpose)
    return PURPOSE_ACCOUNT_POOLS[validated]


def mask_phone(phone: str) -> str:
    if len(phone) <= 4:
        return "*" * len(phone)
    return f"{phone[:4]}{'*' * max(len(phone) - 6, 1)}{phone[-2:]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
