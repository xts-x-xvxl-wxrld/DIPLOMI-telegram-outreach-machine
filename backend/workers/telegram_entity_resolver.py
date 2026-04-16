from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.settings import Settings, get_settings
from backend.db.enums import TelegramEntityType
from backend.services.seed_resolution import ResolverAccountBanned
from backend.services.telegram_entity_intake import (
    TelegramEntityInfo,
    TelegramEntityResolveOutcome,
)
from backend.workers.account_manager import AccountLease
from backend.workers.telegram_resolver import (
    _channel_details,
    _chat_details,
    _classify_telethon_exception,
    _normalize_username,
)


class TelethonEntityResolverError(RuntimeError):
    pass


class TelethonTelegramEntityResolver:
    def __init__(self, lease: AccountLease, *, settings: Settings | None = None) -> None:
        self.lease = lease
        self.settings = settings or get_settings()
        self._client: Any | None = None

    async def resolve_entity(self, username: str) -> TelegramEntityResolveOutcome:
        client = await self._get_client()
        try:
            entity = await client.get_entity(_normalize_username(username))
        except ValueError as exc:
            return TelegramEntityResolveOutcome.inaccessible(str(exc))
        except Exception as exc:
            return _entity_outcome_from_seed_outcome(_classify_telethon_exception(exc))

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
            raise TelethonEntityResolverError(
                "telethon must be installed before telegram_entity.resolve can run"
            ) from exc

        if not self.settings.telegram_api_id or not self.settings.telegram_api_hash:
            raise TelethonEntityResolverError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

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

    async def _outcome_from_entity(self, client: Any, entity: Any) -> TelegramEntityResolveOutcome:
        try:
            from telethon.tl.types import Channel, Chat, User
        except ImportError as exc:
            raise TelethonEntityResolverError("telethon entity types are unavailable") from exc

        if isinstance(entity, User):
            return TelegramEntityResolveOutcome.resolved(
                TelegramEntityInfo(
                    entity_type=TelegramEntityType.BOT
                    if bool(getattr(entity, "bot", False))
                    else TelegramEntityType.USER,
                    tg_id=int(entity.id),
                    username=getattr(entity, "username", None),
                    title=None,
                    first_name=getattr(entity, "first_name", None),
                )
            )

        if isinstance(entity, Channel):
            description, member_count = await _channel_details(client, entity)
            is_group = bool(getattr(entity, "megagroup", False) or getattr(entity, "gigagroup", False))
            return TelegramEntityResolveOutcome.resolved(
                TelegramEntityInfo(
                    entity_type=TelegramEntityType.GROUP
                    if is_group
                    else TelegramEntityType.CHANNEL,
                    tg_id=int(entity.id),
                    username=getattr(entity, "username", None),
                    title=getattr(entity, "title", None),
                    description=description,
                    member_count=member_count,
                    is_group=is_group,
                    is_broadcast=bool(getattr(entity, "broadcast", False)),
                )
            )

        if isinstance(entity, Chat):
            description, member_count = await _chat_details(client, entity)
            return TelegramEntityResolveOutcome.resolved(
                TelegramEntityInfo(
                    entity_type=TelegramEntityType.GROUP,
                    tg_id=int(entity.id),
                    username=None,
                    title=getattr(entity, "title", None),
                    description=description,
                    member_count=member_count,
                    is_group=True,
                    is_broadcast=False,
                )
            )

        return TelegramEntityResolveOutcome.failed(
            f"Resolved target type is not supported: {type(entity).__name__}"
        )


def _entity_outcome_from_seed_outcome(outcome: Any) -> TelegramEntityResolveOutcome:
    if outcome.status == "inaccessible":
        return TelegramEntityResolveOutcome.inaccessible(outcome.error_message)
    if outcome.status == "invalid":
        return TelegramEntityResolveOutcome.invalid(outcome.error_message)
    return TelegramEntityResolveOutcome.failed(outcome.error_message)


def _session_path(session_file_path: str, sessions_dir: str) -> Path:
    path = Path(session_file_path)
    if path.is_absolute():
        return path
    return Path(sessions_dir) / path
