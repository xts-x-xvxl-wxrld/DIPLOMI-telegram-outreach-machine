from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.schemas import JobResponse
from backend.api.deps import DbSession, SettingsDep, require_bot_token
from backend.queue.client import QueueUnavailable, enqueue_account_health_refresh
from backend.services.telegram_account_onboarding import (
    AccountOnboardingError,
    complete_telegram_account_onboarding,
    start_telegram_account_onboarding,
)

router = APIRouter(dependencies=[Depends(require_bot_token)])


class AccountOnboardingStartRequest(BaseModel):
    account_pool: str = Field(min_length=1, max_length=32)
    phone: str = Field(min_length=3, max_length=64)
    session_name: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=1000)
    requested_by: str | None = Field(default=None, max_length=200)


class AccountOnboardingStartResponse(BaseModel):
    status: str
    account_pool: str
    phone: str
    session_file_name: str
    phone_code_hash: str


class AccountOnboardingCompleteRequest(BaseModel):
    account_pool: str = Field(min_length=1, max_length=32)
    phone: str = Field(min_length=3, max_length=64)
    session_name: str = Field(min_length=1, max_length=128)
    phone_code_hash: str = Field(min_length=1, max_length=512)
    code: str = Field(min_length=1, max_length=64)
    password: str | None = Field(default=None, max_length=512)
    notes: str | None = Field(default=None, max_length=1000)
    requested_by: str | None = Field(default=None, max_length=200)


class AccountOnboardingCompleteResponse(BaseModel):
    status: str
    account_pool: str
    phone: str
    session_file_name: str


class AccountHealthRefreshJobRequest(BaseModel):
    spot_check_limit: int = Field(default=2, ge=0, le=10)


@router.post(
    "/telegram-accounts/onboarding/start",
    response_model=AccountOnboardingStartResponse,
)
async def post_account_onboarding_start(
    request: AccountOnboardingStartRequest,
    settings: SettingsDep,
) -> AccountOnboardingStartResponse:
    try:
        result = await start_telegram_account_onboarding(
            settings=settings,
            account_pool=request.account_pool,
            phone=request.phone,
            session_name=request.session_name,
        )
    except AccountOnboardingError as exc:
        raise _onboarding_http_exception(exc) from exc
    return AccountOnboardingStartResponse(**result.__dict__)


@router.post(
    "/telegram-accounts/onboarding/complete",
    response_model=AccountOnboardingCompleteResponse,
)
async def post_account_onboarding_complete(
    request: AccountOnboardingCompleteRequest,
    db: DbSession,
    settings: SettingsDep,
) -> AccountOnboardingCompleteResponse:
    try:
        result = await complete_telegram_account_onboarding(
            db=db,
            settings=settings,
            account_pool=request.account_pool,
            phone=request.phone,
            session_name=request.session_name,
            phone_code_hash=request.phone_code_hash,
            code=request.code,
            password=request.password,
            notes=request.notes,
        )
        await db.commit()
    except AccountOnboardingError as exc:
        await db.rollback()
        raise _onboarding_http_exception(exc) from exc
    return AccountOnboardingCompleteResponse(**result.__dict__)


@router.post(
    "/telegram-accounts/health-refresh-jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_account_health_refresh_job(
    request: AccountHealthRefreshJobRequest,
) -> JobResponse:
    try:
        job = enqueue_account_health_refresh(spot_check_limit=request.spot_check_limit)
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


def _onboarding_http_exception(exc: AccountOnboardingError) -> HTTPException:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code in {"telegram_api_unconfigured", "telethon_not_installed"}:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": exc.message},
    )
