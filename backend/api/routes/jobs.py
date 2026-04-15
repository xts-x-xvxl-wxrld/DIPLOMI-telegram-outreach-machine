from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from backend.api.deps import DbSession, SettingsDep, require_bot_token
from backend.api.schemas import AccountDebugItem, AccountDebugResponse, JobStatusResponse
from backend.db.enums import AccountStatus
from backend.db.models import TelegramAccount
from backend.queue.client import QueueUnavailable, fetch_job_status
from backend.workers.account_manager import mask_phone

router = APIRouter(dependencies=[Depends(require_bot_token)])


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str, settings: SettingsDep) -> JobStatusResponse:
    try:
        job_status = fetch_job_status(job_id, redis_url=settings.redis_url)
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if job_status is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Job not found"})
    return JobStatusResponse(**job_status)


@router.get("/debug/accounts", response_model=AccountDebugResponse)
async def debug_accounts(db: DbSession) -> AccountDebugResponse:
    accounts = list((await db.scalars(select(TelegramAccount).order_by(TelegramAccount.added_at))).all())
    counts = {status.value: 0 for status in AccountStatus}
    for account in accounts:
        counts[account.status] = counts.get(account.status, 0) + 1

    return AccountDebugResponse(
        counts=counts,
        items=[
            AccountDebugItem(
                id=account.id,
                phone=mask_phone(account.phone),
                status=account.status,
                flood_wait_until=account.flood_wait_until,
                last_used_at=account.last_used_at,
                last_error=account.last_error,
            )
            for account in accounts
        ],
    )
