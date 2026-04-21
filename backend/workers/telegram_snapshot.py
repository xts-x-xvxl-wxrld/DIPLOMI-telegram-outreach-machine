from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.settings import Settings, get_settings
from backend.db.models import Community
from backend.services.community_snapshot import (
    CommunitySnapshotError,
    SnapshotAccountBanned,
    SnapshotAccountRateLimited,
    TelegramCommunitySnapshot,
    TelegramMemberInfo,
    TelegramSnapshotCommunity,
)
from backend.workers.account_manager import AccountLease


class TelethonSnapshotError(RuntimeError):
    pass


class TelethonCommunitySnapshotter:
    def __init__(self, lease: AccountLease, *, settings: Settings | None = None) -> None:
        self.lease = lease
        self.settings = settings or get_settings()
        self._client: Any | None = None

    async def snapshot(self, community: Community, *, member_limit: int) -> TelegramCommunitySnapshot:
        client = await self._get_client()
        entity = await self._get_entity(client, community)
        captured_community = await _community_from_entity(client, entity, fallback=community)
        members, notes = await self._snapshot_members(client, entity, member_limit=member_limit)
        member_count = captured_community.member_count
        member_limit_reached = len(members) >= member_limit and (
            member_count is None or member_count > len(members)
        )
        return TelegramCommunitySnapshot(
            community=captured_community,
            members=members,
            member_limit_reached=member_limit_reached,
            snapshot_notes=notes,
        )

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
            raise TelethonSnapshotError("telethon must be installed before community.snapshot can run") from exc

        if not self.settings.telegram_api_id or not self.settings.telegram_api_hash:
            raise TelethonSnapshotError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

        session_path = _session_path(self.lease.session_file_path, self.settings.sessions_dir)
        self._client = TelegramClient(
            str(session_path),
            int(self.settings.telegram_api_id),
            self.settings.telegram_api_hash,
        )
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise SnapshotAccountBanned("Telegram session is not authorized")
        return self._client

    async def _get_entity(self, client: Any, community: Community) -> Any:
        target: str | int
        if community.username:
            target = community.username
        else:
            target = community.tg_id

        try:
            return await client.get_entity(target)
        except Exception as exc:
            _raise_snapshot_exception(exc)

    async def _snapshot_members(
        self,
        client: Any,
        entity: Any,
        *,
        member_limit: int,
    ) -> tuple[list[TelegramMemberInfo], list[str]]:
        members: list[TelegramMemberInfo] = []
        notes: list[str] = []
        try:
            async for user in client.iter_participants(entity, limit=member_limit):
                tg_user_id = getattr(user, "id", None)
                if tg_user_id is None:
                    continue
                members.append(
                    TelegramMemberInfo(
                        tg_user_id=int(tg_user_id),
                        username=getattr(user, "username", None),
                        first_name=getattr(user, "first_name", None),
                    )
                )
        except Exception as exc:
            if _is_account_level_exception(exc):
                _raise_snapshot_exception(exc)
            notes.append(f"Member list was not fully accessible: {exc}")
        return members, notes


async def _community_from_entity(
    client: Any,
    entity: Any,
    *,
    fallback: Community,
) -> TelegramSnapshotCommunity:
    try:
        from telethon.tl.types import Channel, Chat
    except ImportError as exc:
        raise TelethonSnapshotError("telethon entity types are unavailable") from exc

    if isinstance(entity, Channel):
        description, member_count = await _channel_details(client, entity)
        return TelegramSnapshotCommunity(
            tg_id=int(entity.id),
            username=getattr(entity, "username", None) or fallback.username,
            title=getattr(entity, "title", None) or fallback.title,
            description=description,
            member_count=member_count or fallback.member_count,
            is_group=bool(getattr(entity, "megagroup", False) or getattr(entity, "gigagroup", False)),
            is_broadcast=bool(getattr(entity, "broadcast", False)),
        )

    if isinstance(entity, Chat):
        description, member_count = await _chat_details(client, entity)
        return TelegramSnapshotCommunity(
            tg_id=int(entity.id),
            username=fallback.username,
            title=getattr(entity, "title", None) or fallback.title,
            description=description,
            member_count=member_count or fallback.member_count,
            is_group=True,
            is_broadcast=False,
        )

    raise CommunitySnapshotError(f"Resolved target is not a supported community: {type(entity).__name__}")


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


def _entity_member_count(entity: Any) -> int | None:
    value = getattr(entity, "participants_count", None)
    if isinstance(value, int):
        return value
    return None


def _raise_snapshot_exception(exc: Exception) -> None:
    name = exc.__class__.__name__.lower()
    seconds = getattr(exc, "seconds", None)
    if "floodwait" in name or "flood_wait" in name:
        raise SnapshotAccountRateLimited(int(seconds or 0), str(exc)) from exc
    if any(marker in name for marker in ("banned", "deactivated", "authkey", "sessionrevoked")):
        raise SnapshotAccountBanned(str(exc)) from exc
    if any(marker in name for marker in ("private", "invalid", "notoccupied", "occupied")):
        raise CommunitySnapshotError(str(exc)) from exc
    raise CommunitySnapshotError(str(exc)) from exc


def _is_account_level_exception(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    return (
        "floodwait" in name
        or "flood_wait" in name
        or any(marker in name for marker in ("banned", "deactivated", "authkey", "sessionrevoked"))
    )


def _session_path(session_file_path: str, sessions_dir: str) -> Path:
    path = Path(session_file_path)
    if path.is_absolute():
        return path
    return Path(sessions_dir) / path
