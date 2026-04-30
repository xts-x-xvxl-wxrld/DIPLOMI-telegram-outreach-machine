from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import AccountPool, AccountStatus, CommunityAccountMembershipStatus
from backend.db.models import Community, CommunityAccountMembership, TelegramAccount
from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import AccountHealthRefreshPayload
from backend.workers.account_manager import recover_stale_leases
from backend.workers.telegram_engagement import (
    EngagementAccountBanned,
    EngagementAccountRateLimited,
    TelethonTelegramEngagementAdapter,
)

HealthRefreshOutcome = Literal["healthy", "rate_limited", "banned", "error"]


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


class AccountHealthAdapter(Protocol):
    async def check_account_health(
        self,
        *,
        session_file_path: str,
        joined_communities: list[Community] | None = None,
    ) -> None:
        pass

    async def aclose(self) -> None:
        pass


@dataclass
class AccountHealthRefreshSummary:
    accounts_checked: int = 0
    accounts_refreshed: int = 0
    skipped_disabled: int = 0
    skipped_in_use: int = 0
    rate_limited: int = 0
    banned: int = 0
    errors: int = 0
    stale_leases_recovered: int = 0
    refreshed_account_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "processed",
            "job_type": "account.health_refresh",
            "accounts_checked": self.accounts_checked,
            "accounts_refreshed": self.accounts_refreshed,
            "skipped_disabled": self.skipped_disabled,
            "skipped_in_use": self.skipped_in_use,
            "rate_limited": self.rate_limited,
            "banned": self.banned,
            "errors": self.errors,
            "stale_leases_recovered": self.stale_leases_recovered,
            "refreshed_account_ids": self.refreshed_account_ids,
        }


async def process_account_health_refresh(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    adapter_factory: Callable[[], AccountHealthAdapter] = TelethonTelegramEngagementAdapter,
    now: datetime | None = None,
) -> dict[str, object]:
    validated_payload = AccountHealthRefreshPayload.model_validate(payload)
    current_time = _ensure_aware_utc(now or datetime.now(timezone.utc))
    summary = AccountHealthRefreshSummary()

    async with session_factory() as session:
        summary.stale_leases_recovered = await recover_stale_leases(session, now=current_time)
        accounts = await load_account_health_refresh_targets(
            session,
            account_ids=validated_payload.account_ids,
        )
        for account in accounts:
            summary.accounts_checked += 1
            skip_reason = account_health_refresh_skip_reason(account, now=current_time)
            if skip_reason is not None:
                _record_skip(summary, skip_reason)
                continue

            communities = await load_joined_spot_check_communities(
                session,
                account_id=account.id,
                limit=validated_payload.spot_check_limit,
            )
            await _refresh_one_account(
                account,
                communities=communities,
                adapter_factory=adapter_factory,
                summary=summary,
                now=current_time,
            )
        await session.commit()

    return summary.to_dict()


async def load_account_health_refresh_targets(
    session: AsyncSession,
    *,
    account_ids: list[UUID],
) -> list[TelegramAccount]:
    query = select(TelegramAccount).order_by(TelegramAccount.added_at.asc())
    if account_ids:
        query = query.where(TelegramAccount.id.in_(account_ids))
    return list(await session.scalars(query))


async def load_joined_spot_check_communities(
    session: AsyncSession,
    *,
    account_id: UUID,
    limit: int,
) -> list[Community]:
    if limit <= 0:
        return []
    return list(
        await session.scalars(
            select(Community)
            .join(CommunityAccountMembership, CommunityAccountMembership.community_id == Community.id)
            .where(
                CommunityAccountMembership.telegram_account_id == account_id,
                CommunityAccountMembership.status == CommunityAccountMembershipStatus.JOINED.value,
            )
            .order_by(CommunityAccountMembership.last_checked_at.asc().nullsfirst())
            .limit(limit)
        )
    )


def account_health_refresh_skip_reason(account: TelegramAccount, *, now: datetime) -> str | None:
    if account.account_pool == AccountPool.DISABLED.value:
        return "disabled"
    if account.status == AccountStatus.IN_USE.value:
        return "in_use"
    if account.lease_owner is None:
        return None
    if account.lease_expires_at is None:
        return "in_use"
    if _ensure_aware_utc(account.lease_expires_at) > _ensure_aware_utc(now):
        return "in_use"
    return None


def apply_account_health_refresh_outcome(
    account: TelegramAccount,
    *,
    outcome: HealthRefreshOutcome,
    now: datetime,
    flood_wait_seconds: int | None = None,
    error_message: str | None = None,
) -> None:
    current_time = _ensure_aware_utc(now)
    account.lease_owner = None
    account.lease_expires_at = None
    account.last_error = error_message
    if outcome == "healthy":
        account.status = AccountStatus.AVAILABLE.value
        account.flood_wait_until = None
        account.last_error = None
        return
    if outcome == "rate_limited":
        if flood_wait_seconds is None:
            raise ValueError("flood_wait_seconds is required for rate_limited outcome")
        account.status = AccountStatus.RATE_LIMITED.value
        account.flood_wait_until = current_time + timedelta(seconds=flood_wait_seconds)
        return
    if outcome == "banned":
        account.status = AccountStatus.BANNED.value
        account.flood_wait_until = None
        return
    if outcome == "error":
        return
    raise ValueError(f"Unknown health refresh outcome: {outcome}")


def run_account_health_refresh_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_account_health_refresh(payload))


async def _refresh_one_account(
    account: TelegramAccount,
    *,
    communities: list[Community],
    adapter_factory: Callable[[], AccountHealthAdapter],
    summary: AccountHealthRefreshSummary,
    now: datetime,
) -> None:
    adapter = adapter_factory()
    try:
        await adapter.check_account_health(
            session_file_path=account.session_file_path,
            joined_communities=communities,
        )
    except EngagementAccountRateLimited as exc:
        apply_account_health_refresh_outcome(
            account,
            outcome="rate_limited",
            now=now,
            flood_wait_seconds=max(exc.flood_wait_seconds, 0),
            error_message=str(exc),
        )
        summary.rate_limited += 1
    except EngagementAccountBanned as exc:
        apply_account_health_refresh_outcome(account, outcome="banned", now=now, error_message=str(exc))
        summary.banned += 1
    except Exception as exc:
        apply_account_health_refresh_outcome(account, outcome="error", now=now, error_message=str(exc))
        summary.errors += 1
    else:
        apply_account_health_refresh_outcome(account, outcome="healthy", now=now)
        summary.accounts_refreshed += 1
    finally:
        await adapter.aclose()
    summary.refreshed_account_ids.append(str(account.id))


def _record_skip(summary: AccountHealthRefreshSummary, reason: str) -> None:
    if reason == "disabled":
        summary.skipped_disabled += 1
    elif reason == "in_use":
        summary.skipped_in_use += 1


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
