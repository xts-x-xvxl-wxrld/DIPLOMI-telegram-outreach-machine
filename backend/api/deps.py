from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import Settings, get_settings
from backend.db.session import get_db_session

bearer_scheme = HTTPBearer(auto_error=False)


def settings_dep() -> Settings:
    return get_settings()


async def db_session_dep() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session


def require_bot_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> None:
    if not settings.bot_api_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "auth_not_configured", "message": "BOT_API_TOKEN is not configured"},
        )
    if credentials is None or credentials.credentials != settings.bot_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid API token"},
        )


DbSession = Annotated[AsyncSession, Depends(db_session_dep)]
SettingsDep = Annotated[Settings, Depends(settings_dep)]
BotAuth = Annotated[None, Depends(require_bot_token)]

