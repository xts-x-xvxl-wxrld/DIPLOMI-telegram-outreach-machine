from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from backend.api.deps import DbSession, SettingsDep
from backend.queue.client import ping_redis

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: DbSession, settings: SettingsDep) -> dict[str, str]:
    postgres = "ok"
    redis = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        postgres = "error"

    try:
        ping_redis(settings.redis_url)
    except Exception:
        redis = "error"

    return {
        "status": "ok" if postgres == "ok" and redis == "ok" else "degraded",
        "postgres": postgres,
        "redis": redis,
    }

