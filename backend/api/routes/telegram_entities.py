from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import DbSession, require_bot_token
from backend.api.schemas import (
    TelegramEntityIntakeOut,
    TelegramEntityIntakeRequest,
    TelegramEntityIntakeResponse,
)
from backend.db.models import TelegramEntityIntake
from backend.queue.client import QueueUnavailable, enqueue_telegram_entity_resolve
from backend.services.telegram_entity_intake import create_or_reset_intake

router = APIRouter(dependencies=[Depends(require_bot_token)])


@router.post("/telegram-entities", response_model=TelegramEntityIntakeResponse, status_code=202)
async def create_telegram_entity_intake(
    payload: TelegramEntityIntakeRequest,
    db: DbSession,
) -> TelegramEntityIntakeResponse:
    try:
        intake = await create_or_reset_intake(
            db,
            payload.handle,
            requested_by=payload.requested_by or "telegram_bot",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_telegram_handle", "message": str(exc)},
        ) from exc

    await db.commit()
    try:
        job = enqueue_telegram_entity_resolve(
            intake.id,
            requested_by=payload.requested_by or "telegram_bot",
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TelegramEntityIntakeResponse(intake=TelegramEntityIntakeOut.model_validate(intake), job=job)


@router.get("/telegram-entities/{intake_id}", response_model=TelegramEntityIntakeOut)
async def get_telegram_entity_intake(intake_id: UUID, db: DbSession) -> TelegramEntityIntakeOut:
    intake = await db.get(TelegramEntityIntake, intake_id)
    if intake is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Telegram entity intake not found"},
        )
    return TelegramEntityIntakeOut.model_validate(intake)
