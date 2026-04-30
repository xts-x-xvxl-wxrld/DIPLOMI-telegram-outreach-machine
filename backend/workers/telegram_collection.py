from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.settings import Settings, get_settings
from backend.db.models import Community
from backend.services.community_collection import (
    CollectionAccountBanned,
    CollectionAccountRateLimited,
    CollectionCommunityInaccessible,
    TelegramCollectedMessage,
    TelegramCollectedUser,
    TelegramCollectionBatch,
    TelegramCollectionMetadata,
)
from backend.workers.account_manager import AccountLease


class TelethonCollectionError(RuntimeError):
    pass


class TelethonEngagementCollector:
    def __init__(self, lease: AccountLease, *, settings: Settings | None = None) -> None:
        self.lease = lease
        self.settings = settings or get_settings()
        self._client: Any | None = None

    async def collect_messages(
        self,
        community: Community,
        *,
        after_tg_message_id: int | None,
        limit: int,
    ) -> TelegramCollectionBatch:
        client = await self._get_client()
        entity = await self._get_entity(client, community)
        metadata = await _metadata_from_entity(client, entity, fallback=community)
        messages: list[TelegramCollectedMessage] = []
        try:
            async for raw_message in client.iter_messages(
                entity,
                limit=limit,
                min_id=after_tg_message_id or 0,
                reverse=True,
            ):
                collected = await _message_from_telethon(client, entity, raw_message, community=community)
                if collected is not None:
                    messages.append(collected)
        except Exception as exc:
            _raise_collection_exception(exc)
        return TelegramCollectionBatch(messages=messages, metadata=metadata)

    async def acknowledge_read(
        self,
        community: Community,
        *,
        max_tg_message_id: int,
    ) -> None:
        client = await self._get_client()
        entity = await self._get_entity(client, community)
        mark_read = getattr(client, "send_read_acknowledge", None)
        if not callable(mark_read):
            return
        try:
            await mark_read(entity, max_id=max_tg_message_id)
        except Exception:
            return

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
            raise TelethonCollectionError("telethon must be installed before collection.run can run") from exc

        if not self.settings.telegram_api_id or not self.settings.telegram_api_hash:
            raise TelethonCollectionError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

        session_path = _session_path(self.lease.session_file_path, self.settings.sessions_dir)
        self._client = TelegramClient(
            str(session_path),
            int(self.settings.telegram_api_id),
            self.settings.telegram_api_hash,
        )
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise CollectionAccountBanned("Telegram session is not authorized")
        return self._client

    async def _get_entity(self, client: Any, community: Community) -> Any:
        target: str | int = community.username or community.tg_id
        try:
            return await client.get_entity(target)
        except Exception as exc:
            _raise_collection_exception(exc)


async def _message_from_telethon(
    client: Any,
    entity: Any,
    raw_message: Any,
    *,
    community: Community,
) -> TelegramCollectedMessage | None:
    tg_message_id = getattr(raw_message, "id", None)
    message_date = getattr(raw_message, "date", None)
    if tg_message_id is None or message_date is None:
        return None
    text = getattr(raw_message, "message", None)
    if not isinstance(text, str) or not text.strip():
        return None

    reply_to_tg_message_id = getattr(raw_message, "reply_to_msg_id", None)
    reply_context = await _load_reply_context(client, entity, reply_to_tg_message_id)
    sender = await _sender_from_message(raw_message)
    return TelegramCollectedMessage(
        tg_message_id=int(tg_message_id),
        text=text,
        message_date=message_date,
        message_type="text",
        sender=sender,
        reply_to_tg_message_id=int(reply_to_tg_message_id) if reply_to_tg_message_id else None,
        reply_context=reply_context,
        is_replyable=bool(community.is_group and tg_message_id is not None),
        has_forward=getattr(raw_message, "fwd_from", None) is not None,
        views=getattr(raw_message, "views", None),
        reactions_count=_reaction_count(getattr(raw_message, "reactions", None)),
    )


async def _sender_from_message(raw_message: Any) -> TelegramCollectedUser | None:
    sender_id = getattr(raw_message, "sender_id", None)
    if sender_id is None:
        return None
    try:
        sender = await raw_message.get_sender()
    except Exception:
        sender = None
    return TelegramCollectedUser(
        tg_user_id=int(sender_id),
        username=getattr(sender, "username", None),
        first_name=getattr(sender, "first_name", None),
    )


async def _load_reply_context(client: Any, entity: Any, reply_to_tg_message_id: object) -> str | None:
    if reply_to_tg_message_id is None:
        return None
    try:
        replied = await client.get_messages(entity, ids=int(reply_to_tg_message_id))
    except Exception:
        return None
    text = getattr(replied, "message", None)
    return text if isinstance(text, str) and text.strip() else None


async def _metadata_from_entity(
    client: Any,
    entity: Any,
    *,
    fallback: Community,
) -> TelegramCollectionMetadata:
    description, member_count = await _entity_details(client, entity)
    return TelegramCollectionMetadata(
        username=getattr(entity, "username", None) or fallback.username,
        title=getattr(entity, "title", None) or fallback.title,
        description=description or fallback.description,
        member_count=member_count or fallback.member_count,
        is_group=bool(
            getattr(entity, "megagroup", False)
            or getattr(entity, "gigagroup", False)
            or entity.__class__.__name__ == "Chat"
        ),
        is_broadcast=bool(getattr(entity, "broadcast", False)),
    )


async def _entity_details(client: Any, entity: Any) -> tuple[str | None, int | None]:
    try:
        from telethon.tl.functions.channels import GetFullChannelRequest
        from telethon.tl.functions.messages import GetFullChatRequest
        from telethon.tl.types import Channel, Chat
    except ImportError:
        return None, _entity_member_count(entity)

    try:
        if isinstance(entity, Channel):
            full = await client(GetFullChannelRequest(entity))
        elif isinstance(entity, Chat):
            full = await client(GetFullChatRequest(entity.id))
        else:
            return None, _entity_member_count(entity)
    except Exception:
        return None, _entity_member_count(entity)

    full_chat = getattr(full, "full_chat", None)
    return (
        getattr(full_chat, "about", None),
        getattr(full_chat, "participants_count", None) or _entity_member_count(entity),
    )


def _reaction_count(reactions: Any) -> int | None:
    results = getattr(reactions, "results", None)
    if not results:
        return None
    total = 0
    for result in results:
        count = getattr(result, "count", None)
        if isinstance(count, int):
            total += count
    return total


def _entity_member_count(entity: Any) -> int | None:
    value = getattr(entity, "participants_count", None)
    return value if isinstance(value, int) else None


def _raise_collection_exception(exc: Exception) -> None:
    name = exc.__class__.__name__.lower()
    seconds = getattr(exc, "seconds", None)
    if "floodwait" in name or "flood_wait" in name:
        raise CollectionAccountRateLimited(int(seconds or 0), str(exc)) from exc
    if any(marker in name for marker in ("banned", "deactivated", "authkey", "sessionrevoked")):
        raise CollectionAccountBanned(str(exc)) from exc
    if any(marker in name for marker in ("private", "invalid", "notoccupied", "occupied", "forbidden")):
        raise CollectionCommunityInaccessible(str(exc)) from exc
    raise CollectionCommunityInaccessible(str(exc)) from exc


def _session_path(session_file_path: str, sessions_dir: str) -> Path:
    path = Path(session_file_path)
    if path.is_absolute():
        return path
    return Path(sessions_dir) / path


__all__ = [
    "TelethonCollectionError",
    "TelethonEngagementCollector",
]
