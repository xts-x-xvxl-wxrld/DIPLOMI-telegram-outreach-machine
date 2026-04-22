from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.settings import Settings, get_settings
from backend.services.search_retrieval import (
    EntitySearchEvidence,
    TelegramEntitySearchError,
    TelegramEntitySearchHit,
)
from backend.services.seed_resolution import ResolverAccountBanned, ResolverAccountRateLimited
from backend.workers.account_manager import AccountLease
from backend.workers.telegram_resolver import _channel_details, _chat_details


class TelethonTelegramEntitySearchAdapter:
    def __init__(self, lease: AccountLease, *, settings: Settings | None = None) -> None:
        self.lease = lease
        self.settings = settings or get_settings()
        self._client: Any | None = None

    async def search_entities(self, query_text: str, *, limit: int) -> list[TelegramEntitySearchHit]:
        client = await self._get_client()
        try:
            from telethon.tl.functions.contacts import SearchRequest

            result = await client(SearchRequest(q=query_text, limit=limit))
        except Exception as exc:
            _raise_adapter_exception(exc)

        hits: list[TelegramEntitySearchHit] = []
        for entity in list(getattr(result, "chats", []) or []) + list(getattr(result, "users", []) or []):
            hits.append(await self._hit_from_entity(client, entity, query_text=query_text))
            if len(hits) >= limit:
                break
        return hits

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
            raise TelegramEntitySearchError(
                "telethon must be installed before search.retrieve can run"
            ) from exc

        if not self.settings.telegram_api_id or not self.settings.telegram_api_hash:
            raise TelegramEntitySearchError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

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

    async def _hit_from_entity(
        self,
        client: Any,
        entity: Any,
        *,
        query_text: str,
    ) -> TelegramEntitySearchHit:
        try:
            from telethon.tl.types import Channel, Chat, User
        except ImportError as exc:
            raise TelegramEntitySearchError("telethon entity types are unavailable") from exc

        if isinstance(entity, User):
            return TelegramEntitySearchHit(
                status="not_community",
                tg_id=int(entity.id),
                username=getattr(entity, "username", None),
                title=getattr(entity, "first_name", None),
                error_message="Telegram entity search hit is a user or bot",
                metadata={"entity_type": "user", "query_text": query_text},
            )

        if isinstance(entity, Channel):
            description, member_count = await _channel_details(client, entity)
            username = getattr(entity, "username", None)
            title = getattr(entity, "title", None)
            return TelegramEntitySearchHit(
                tg_id=int(entity.id),
                username=username,
                canonical_url=f"https://t.me/{username}" if username else None,
                title=title,
                description=description,
                member_count=member_count,
                is_group=bool(getattr(entity, "megagroup", False) or getattr(entity, "gigagroup", False)),
                is_broadcast=bool(getattr(entity, "broadcast", False)),
                evidence=_adapter_evidence(query_text=query_text, title=title, username=username),
                metadata={"entity_type": "channel"},
            )

        if isinstance(entity, Chat):
            description, member_count = await _chat_details(client, entity)
            title = getattr(entity, "title", None)
            return TelegramEntitySearchHit(
                tg_id=int(entity.id),
                title=title,
                description=description,
                member_count=member_count,
                is_group=True,
                is_broadcast=False,
                evidence=_adapter_evidence(query_text=query_text, title=title, username=None),
                metadata={"entity_type": "chat"},
            )

        return TelegramEntitySearchHit(
            status="not_community",
            error_message=f"Unsupported Telegram entity type: {type(entity).__name__}",
            metadata={"entity_type": type(entity).__name__, "query_text": query_text},
        )


def _adapter_evidence(
    *,
    query_text: str,
    title: str | None,
    username: str | None,
) -> tuple[EntitySearchEvidence, ...]:
    evidence: list[EntitySearchEvidence] = []
    query = query_text.casefold()
    if title and any(term in title.casefold() for term in query.split()):
        evidence.append(
            EntitySearchEvidence(
                "entity_title_match",
                title,
                {"field": "title", "source": "telegram_entity_search"},
            )
        )
    if username and any(term in username.casefold() for term in query.split()):
        evidence.append(
            EntitySearchEvidence(
                "entity_username_match",
                f"@{username}",
                {"field": "username", "source": "telegram_entity_search"},
            )
        )
    return tuple(evidence)


def _raise_adapter_exception(exc: Exception) -> None:
    name = exc.__class__.__name__.lower()
    seconds = getattr(exc, "seconds", None)
    if "floodwait" in name or "flood_wait" in name:
        raise ResolverAccountRateLimited(int(seconds or 0), str(exc)) from exc
    if any(marker in name for marker in ("banned", "deactivated", "authkey", "sessionrevoked")):
        raise ResolverAccountBanned(str(exc)) from exc
    raise TelegramEntitySearchError(str(exc)) from exc


def _session_path(session_file_path: str, sessions_dir: str) -> Path:
    path = Path(session_file_path)
    if path.is_absolute():
        return path
    return Path(sessions_dir) / path


__all__ = ["TelethonTelegramEntitySearchAdapter"]
