from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import Settings, get_settings
from backend.db.session import get_db_session

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class OperatorCapabilities:
    operator_user_id: int | None
    backend_capabilities_available: bool
    engagement_admin: bool | None
    source: str


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


def parse_admin_user_ids(raw_value: str) -> frozenset[int]:
    values: set[int] = set()
    for raw_item in raw_value.replace(",", " ").split():
        item = raw_item.strip()
        if not item:
            continue
        try:
            user_id = int(item)
        except ValueError as exc:
            raise ValueError("ENGAGEMENT_ADMIN_USER_IDS must contain numeric Telegram user IDs") from exc
        if user_id <= 0:
            raise ValueError("ENGAGEMENT_ADMIN_USER_IDS must contain positive Telegram user IDs")
        values.add(user_id)
    return frozenset(values)


def resolve_operator_capabilities(
    settings: Annotated[Settings, Depends(settings_dep)],
    telegram_user_id: Annotated[str | None, Header(alias="X-Telegram-User-Id")] = None,
) -> OperatorCapabilities:
    raw_admin_ids = str(getattr(settings, "engagement_admin_user_ids", "") or "")
    admin_ids = parse_admin_user_ids(raw_admin_ids)
    operator_user_id = _parse_header_user_id(telegram_user_id)

    if not admin_ids:
        return OperatorCapabilities(
            operator_user_id=operator_user_id,
            backend_capabilities_available=False,
            engagement_admin=None,
            source="unconfigured",
        )

    return OperatorCapabilities(
        operator_user_id=operator_user_id,
        backend_capabilities_available=True,
        engagement_admin=operator_user_id in admin_ids if operator_user_id is not None else False,
        source="backend_admin_user_ids",
    )


def require_engagement_admin_capability(
    capabilities: Annotated[OperatorCapabilities, Depends(resolve_operator_capabilities)],
) -> OperatorCapabilities:
    if not capabilities.backend_capabilities_available or capabilities.engagement_admin:
        return capabilities
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "engagement_admin_required",
            "message": "Engagement admin capability is required",
        },
    )


def _parse_header_user_id(raw_value: str | None) -> int | None:
    if raw_value is None or not raw_value.strip():
        return None
    try:
        user_id = int(raw_value.strip())
    except ValueError:
        return None
    return user_id if user_id > 0 else None


DbSession = Annotated[AsyncSession, Depends(db_session_dep)]
SettingsDep = Annotated[Settings, Depends(settings_dep)]
BotAuth = Annotated[None, Depends(require_bot_token)]
OperatorCapabilitiesDep = Annotated[OperatorCapabilities, Depends(resolve_operator_capabilities)]
