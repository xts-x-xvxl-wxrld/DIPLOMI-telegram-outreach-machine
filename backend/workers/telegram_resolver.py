from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.settings import Settings, get_settings
from backend.services.seed_resolution import (
    ResolverAccountBanned,
    ResolverAccountRateLimited,
    TelegramCommunityInfo,
    TelegramResolveOutcome,
)
from backend.workers.account_manager import AccountLease


class TelethonResolverError(RuntimeError):
    pass


class TelethonTelegramResolver:
    def __init__(self, lease: AccountLease, *, settings: Settings | None = None) -> None:
        self.lease = lease
        self.settings = settings or get_settings()
        self._client: Any | None = None

    async def resolve(self, username: str) -> TelegramResolveOutcome:
        client = await self._get_client()
        try:
            entity = await client.get_entity(_normalize_username(username))
        except ValueError as exc:
            return TelegramResolveOutcome.inaccessible(str(exc))
        except Exception as exc:
            return _classify_telethon_exception(exc)

        return await self._outcome_from_entity(client, entity)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None

    async def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from telethon import TelegramClient
        except ImportError as exc:
            raise TelethonResolverError("telethon must be installed before seed.resolve can run") from exc

        if not self.settings.telegram_api_id or not self.settings.telegram_api_hash:
            raise TelethonResolverError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

        session_path = _session_path(self.lease.session_file_path, self.settings.sessions_dir)
        self._client = TelegramClient(
            str(session_path),
            int(self.settings.telegram_api_id),
            self.settings.telegram_api_hash,
        )
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise ResolverAccountBanned("Telegram session is not authorized")
        return self._client

    async def _outcome_from_entity(self, client: Any, entity: Any) -> TelegramResolveOutcome:
        try:
            from telethon.tl.types import Channel, Chat, User
        except ImportError as exc:
            raise TelethonResolverError("telethon entity types are unavailable") from exc

        if isinstance(entity, User):
            return TelegramResolveOutcome.not_community(
                "Resolved target is a Telegram user or bot, not a community"
            )

        if isinstance(entity, Channel):
            description, member_count = await _channel_details(client, entity)
            return TelegramResolveOutcome.resolved(
                TelegramCommunityInfo(
                    tg_id=int(entity.id),
                    username=getattr(entity, "username", None),
                    title=getattr(entity, "title", None),
                    description=description,
                    member_count=member_count,
                    is_group=bool(getattr(entity, "megagroup", False) or getattr(entity, "gigagroup", False)),
                    is_broadcast=bool(getattr(entity, "broadcast", False)),
                )
            )

        if isinstance(entity, Chat):
            description, member_count = await _chat_details(client, entity)
            return TelegramResolveOutcome.resolved(
                TelegramCommunityInfo(
                    tg_id=int(entity.id),
                    username=None,
                    title=getattr(entity, "title", None),
                    description=description,
                    member_count=member_count,
                    is_group=True,
                    is_broadcast=False,
                )
            )

        return TelegramResolveOutcome.not_community(
            f"Resolved target type is not a supported community: {type(entity).__name__}"
        )


async def _channel_details(client: Any, entity: Any) -> tuple[str | None, int | None]:
    try:
        from telethon.tl.functions.channels import GetFullChannelRequest

        full = await client(GetFullChannelRequest(entity))
    except Exception:
        return None, _entity_member_count(entity)

    full_chat = getattr(full, "full_chat", None)
    return (
        getattr(full_chat, "about", None),
        getattr(full_chat, "participants_count", None) or _entity_member_count(entity),
    )


async def _chat_details(client: Any, entity: Any) -> tuple[str | None, int | None]:
    try:
        from telethon.tl.functions.messages import GetFullChatRequest

        full = await client(GetFullChatRequest(entity.id))
    except Exception:
        return None, _entity_member_count(entity)

    full_chat = getattr(full, "full_chat", None)
    return (
        getattr(full_chat, "about", None),
        getattr(full_chat, "participants_count", None) or _entity_member_count(entity),
    )


def _classify_telethon_exception(exc: Exception) -> TelegramResolveOutcome:
    name = exc.__class__.__name__.lower()
    seconds = getattr(exc, "seconds", None)
    if "floodwait" in name or "flood_wait" in name:
        raise ResolverAccountRateLimited(int(seconds or 0), str(exc)) from exc
    if any(marker in name for marker in ("banned", "deactivated", "authkey", "sessionrevoked")):
        raise ResolverAccountBanned(str(exc)) from exc
    if any(marker in name for marker in ("private", "invalid", "notoccupied", "occupied")):
        return TelegramResolveOutcome.inaccessible(str(exc))
    return TelegramResolveOutcome.failed(str(exc))


def _entity_member_count(entity: Any) -> int | None:
    value = getattr(entity, "participants_count", None)
    if isinstance(value, int):
        return value
    return None


def _normalize_username(username: str) -> str:
    return username.strip().lstrip("@")


def _session_path(session_file_path: str, sessions_dir: str) -> Path:
    path = Path(session_file_path)
    if path.is_absolute():
        return path
    return Path(sessions_dir) / path
