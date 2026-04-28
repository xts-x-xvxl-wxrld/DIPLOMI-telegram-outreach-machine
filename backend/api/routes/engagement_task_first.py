# ruff: noqa: F401,F403,F405
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import DbSession, require_bot_token
from backend.api.schemas import (
    TaskFirstEngagementCreateRequest,
    TaskFirstEngagementCreateResponse,
    TaskFirstEngagementOut,
    TaskFirstEngagementPatchRequest,
    TaskFirstEngagementPatchResponse,
    TaskFirstEngagementSettingsOut,
    TaskFirstEngagementSettingsResponse,
    TaskFirstEngagementSettingsUpdate,
    TaskFirstWizardActionRequest,
    TaskFirstWizardConfirmResponse,
    TaskFirstWizardRetryResponse,
)
from backend.queue.client import enqueue_manual_engagement_detect
from backend.services.task_first_engagements import (
    confirm_task_first_engagement,
    create_task_first_engagement,
    patch_task_first_engagement,
    put_task_first_engagement_settings,
    retry_task_first_engagement,
)

router = APIRouter(dependencies=[Depends(require_bot_token)])


@router.post("/engagements", response_model=TaskFirstEngagementCreateResponse, status_code=201)
async def post_task_first_engagement(
    payload: TaskFirstEngagementCreateRequest,
    db: DbSession,
) -> TaskFirstEngagementCreateResponse:
    try:
        result = await create_task_first_engagement(
            db,
            target_id=payload.target_id,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "target_not_found", "message": "Target not found"},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "target_not_resolved", "message": "Target is not resolved"},
        ) from exc

    await db.commit()
    return TaskFirstEngagementCreateResponse(
        result=result.result,
        engagement=TaskFirstEngagementOut.model_validate(result.engagement),
    )


@router.patch("/engagements/{engagement_id}", response_model=TaskFirstEngagementPatchResponse)
async def patch_engagement(
    engagement_id: UUID,
    payload: TaskFirstEngagementPatchRequest,
    db: DbSession,
) -> TaskFirstEngagementPatchResponse:
    result = await patch_task_first_engagement(
        db,
        engagement_id=engagement_id,
        topic_id=payload.topic_id,
        name=payload.name,
        fields_set=set(payload.model_fields_set),
    )
    if result.result == "updated":
        await db.commit()
    return TaskFirstEngagementPatchResponse(
        result=result.result,
        engagement=None if result.engagement is None else TaskFirstEngagementOut.model_validate(result.engagement),
        message=result.message,
        code=result.code,
    )


@router.put(
    "/engagements/{engagement_id}/settings",
    response_model=TaskFirstEngagementSettingsResponse,
)
async def put_task_first_settings(
    engagement_id: UUID,
    payload: TaskFirstEngagementSettingsUpdate,
    db: DbSession,
) -> TaskFirstEngagementSettingsResponse:
    result = await put_task_first_engagement_settings(
        db,
        engagement_id=engagement_id,
        assigned_account_id=payload.assigned_account_id,
        mode=None if payload.mode is None else payload.mode.value,
        quiet_hours_start=payload.quiet_hours_start,
        quiet_hours_end=payload.quiet_hours_end,
        fields_set=set(payload.model_fields_set),
    )
    if result.result == "updated":
        await db.commit()
    return TaskFirstEngagementSettingsResponse(
        result=result.result,
        settings=None if result.settings is None else TaskFirstEngagementSettingsOut.model_validate(result.settings),
        message=result.message,
        code=result.code,
    )


@router.post(
    "/engagements/{engagement_id}/wizard-confirm",
    response_model=TaskFirstWizardConfirmResponse,
)
async def post_task_first_wizard_confirm(
    engagement_id: UUID,
    payload: TaskFirstWizardActionRequest,
    db: DbSession,
) -> TaskFirstWizardConfirmResponse:
    result = await confirm_task_first_engagement(
        db,
        engagement_id=engagement_id,
        requested_by=payload.requested_by or "operator",
        enqueue_detect=enqueue_manual_engagement_detect,
    )
    if result.result == "confirmed":
        await db.commit()
    return TaskFirstWizardConfirmResponse(
        result=result.result,
        message=result.message,
        next_callback=result.next_callback,
        engagement_id=result.engagement_id,
        engagement_status=result.engagement_status,
        target_status=result.target_status,
        field=result.field,
        code=result.code,
    )


@router.post(
    "/engagements/{engagement_id}/wizard-retry",
    response_model=TaskFirstWizardRetryResponse,
)
async def post_task_first_wizard_retry(
    engagement_id: UUID,
    db: DbSession,
) -> TaskFirstWizardRetryResponse:
    result = await retry_task_first_engagement(db, engagement_id=engagement_id)
    if result.result == "reset":
        await db.commit()
    return TaskFirstWizardRetryResponse(
        result=result.result,
        message=result.message,
        next_callback=result.next_callback,
        engagement_id=result.engagement_id,
        code=result.code,
    )


__all__ = [
    "router",
    "patch_engagement",
    "post_task_first_engagement",
    "post_task_first_wizard_confirm",
    "post_task_first_wizard_retry",
    "put_task_first_settings",
]
