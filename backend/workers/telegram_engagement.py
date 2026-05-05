from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from backend.core.settings import Settings, get_settings
from backend.db.models import Community
from backend.services.engagement_account_behavior import INITIAL_JOIN_READ_LIMIT
from backend.workers.account_manager import AccountLease

LOGGER = logging.getLogger(__name__)


class EngagementAccountRateLimited(RuntimeError):
    def __init__(self, flood_wait_seconds: int, message: str | None = None) -> None:
        self.flood_wait_seconds = flood_wait_seconds
        super().__init__(message or f"Telegram account rate limited for {flood_wait_seconds}s")


class EngagementAccountBanned(RuntimeError):
    pass


class EngagementCommunityInaccessible(RuntimeError):
    pass


class EngagementMessageNotReplyable(RuntimeError):
    pass


class TelegramEngagementError(RuntimeError):
    pass


DEFAULT_REPLY_TYPING_SECONDS = 2.0


@dataclass(frozen=True)
class JoinResult:
    status: Literal["joined", "already_joined", "inaccessible"]
    joined_at: datetime | None
    error_message: str | None = None


@dataclass(frozen=True)
class SendResult:
    sent_tg_message_id: int
    sent_at: datetime


@dataclass(frozen=True)
class SourceMessagePreflight:
    source_tg_message_id: int


class TelegramEngagementAdapter(Protocol):
    async def join_community(
        self,
        *,
        session_file_path: str,
        community: Community,
    ) -> JoinResult:
        pass

    async def send_public_reply(
        self,
        *,
        session_file_path: str,
        community: Community,
        reply_to_tg_message_id: int,
        text: str,
    ) -> SendResult:
        pass

    async def verify_reply_source(
        self,
        *,
        session_file_path: str,
        community: Community,
        reply_to_tg_message_id: int,
    ) -> SourceMessagePreflight:
        pass

    async def read_recent_messages_after_join(
        self,
        *,
        session_file_path: str,
        community: Community,
        limit: int = INITIAL_JOIN_READ_LIMIT,
    ) -> int:
        pass

    async def check_account_health(
        self,
        *,
        session_file_path: str,
        joined_communities: list[Community] | None = None,
    ) -> None:
        pass


class TelethonTelegramEngagementAdapter:
    def __init__(
        self,
        lease: AccountLease | None = None,
        *,
        settings: Settings | None = None,
        typing_delay_seconds: float = DEFAULT_REPLY_TYPING_SECONDS,
    ) -> None:
        self.lease = lease
        self.settings = settings or get_settings()
        self.typing_delay_seconds = max(0.0, typing_delay_seconds)
        self._client: Any | None = None

    async def join_community(
        self,
        *,
        session_file_path: str,
        community: Community,
    ) -> JoinResult:
        LOGGER.info(
            "Telethon engagement join starting community_id=%s target=%s telegram_account_id=%s",
            community.id,
            _community_target(community),
            _lease_account_id(self.lease),
        )
        client = await self._get_client(session_file_path)
        target = _community_target(community)
        if target is None:
            return JoinResult(
                status="inaccessible",
                joined_at=None,
                error_message="Community has no public username or Telegram ID",
            )

        try:
            entity = await client.get_entity(target)
        except ValueError as exc:
            return JoinResult(status="inaccessible", joined_at=None, error_message=str(exc))
        except Exception as exc:
            return _classify_telethon_join_exception(exc)

        try:
            from telethon.tl.functions.channels import JoinChannelRequest

            await client(JoinChannelRequest(entity))
        except Exception as exc:
            return _classify_telethon_join_exception(exc)

        result = JoinResult(status="joined", joined_at=_utcnow())
        LOGGER.info(
            "Telethon engagement join finished community_id=%s target=%s status=%s telegram_account_id=%s",
            community.id,
            target,
            result.status,
            _lease_account_id(self.lease),
        )
        return result

    async def send_public_reply(
        self,
        *,
        session_file_path: str,
        community: Community,
        reply_to_tg_message_id: int,
        text: str,
    ) -> SendResult:
        LOGGER.info(
            "Telethon engagement send starting community_id=%s target=%s reply_to_tg_message_id=%s text_len=%s telegram_account_id=%s",
            community.id,
            _community_target(community),
            reply_to_tg_message_id,
            len(text),
            _lease_account_id(self.lease),
        )
        client = await self._get_client(session_file_path)
        entity = await _resolve_send_entity(client, community)

        try:
            await _mark_reply_source_read(
                client,
                entity,
                reply_to_tg_message_id=reply_to_tg_message_id,
            )
            message = await _send_message_with_typing(
                client,
                entity,
                text=text,
                reply_to_tg_message_id=reply_to_tg_message_id,
                typing_delay_seconds=self.typing_delay_seconds,
            )
        except Exception as exc:
            _raise_classified_telethon_send_exception(exc)

        sent_id = getattr(message, "id", None)
        if sent_id is None:
            raise TelegramEngagementError("Telegram send returned no message id")
        sent_at = getattr(message, "date", None)
        if not isinstance(sent_at, datetime):
            sent_at = _utcnow()
        elif sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        result = SendResult(sent_tg_message_id=int(sent_id), sent_at=sent_at)
        LOGGER.info(
            "Telethon engagement send finished community_id=%s sent_tg_message_id=%s telegram_account_id=%s",
            community.id,
            result.sent_tg_message_id,
            _lease_account_id(self.lease),
        )
        return result

    async def verify_reply_source(
        self,
        *,
        session_file_path: str,
        community: Community,
        reply_to_tg_message_id: int,
    ) -> SourceMessagePreflight:
        LOGGER.info(
            "Telethon engagement verify source community_id=%s target=%s reply_to_tg_message_id=%s telegram_account_id=%s",
            community.id,
            _community_target(community),
            reply_to_tg_message_id,
            _lease_account_id(self.lease),
        )
        client = await self._get_client(session_file_path)
        entity = await _resolve_send_entity(client, community)
        try:
            message = await client.get_messages(entity, ids=reply_to_tg_message_id)
        except Exception as exc:
            _raise_classified_telethon_send_exception(exc)
        if message is None:
            raise EngagementMessageNotReplyable("Source message is no longer accessible")
        message_id = getattr(message, "id", None)
        if int(message_id or 0) != int(reply_to_tg_message_id):
            raise EngagementMessageNotReplyable("Source message is no longer accessible")
        if getattr(message, "action", None) is not None:
            raise EngagementMessageNotReplyable("Source message is not replyable")
        result = SourceMessagePreflight(source_tg_message_id=int(reply_to_tg_message_id))
        LOGGER.info(
            "Telethon engagement verified source community_id=%s reply_to_tg_message_id=%s telegram_account_id=%s",
            community.id,
            reply_to_tg_message_id,
            _lease_account_id(self.lease),
        )
        return result

    async def read_recent_messages_after_join(
        self,
        *,
        session_file_path: str,
        community: Community,
        limit: int = INITIAL_JOIN_READ_LIMIT,
    ) -> int:
        if limit <= 0:
            return 0
        LOGGER.info(
            "Telethon engagement post-join read starting community_id=%s target=%s limit=%s telegram_account_id=%s",
            community.id,
            _community_target(community),
            limit,
            _lease_account_id(self.lease),
        )
        client = await self._get_client(session_file_path)
        entity = await _resolve_send_entity(client, community)
        try:
            messages = [
                message
                async for message in client.iter_messages(entity, limit=limit)
                if getattr(message, "id", None) is not None
            ]
            if messages:
                max_id = max(int(message.id) for message in messages)
                await _mark_entity_read(client, entity, max_id=max_id)
            count = len(messages)
            LOGGER.info(
                "Telethon engagement post-join read finished community_id=%s messages_read=%s telegram_account_id=%s",
                community.id,
                count,
                _lease_account_id(self.lease),
            )
            return count
        except Exception:
            return 0

    async def check_account_health(
        self,
        *,
        session_file_path: str,
        joined_communities: list[Community] | None = None,
    ) -> None:
        LOGGER.info(
            "Telethon engagement account health starting telegram_account_id=%s joined_communities=%s",
            _lease_account_id(self.lease),
            len(joined_communities or []),
        )
        client = await self._get_client(session_file_path)
        try:
            identity = await client.get_me()
        except Exception as exc:
            _raise_classified_telethon_account_exception(exc)
        if identity is None:
            raise EngagementAccountBanned("Telegram session returned no account identity")

        for community in joined_communities or []:
            await _spot_check_joined_community(client, community)
        LOGGER.info(
            "Telethon engagement account health finished telegram_account_id=%s joined_communities=%s",
            _lease_account_id(self.lease),
            len(joined_communities or []),
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None

    async def _get_client(self, session_file_path: str) -> Any:
        if self._client is not None:
            return self._client

        try:
            from telethon import TelegramClient
        except ImportError as exc:
            raise TelegramEngagementError(
                "telethon must be installed before community.join can run"
            ) from exc

        if not self.settings.telegram_api_id or not self.settings.telegram_api_hash:
            raise TelegramEngagementError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

        session_path = _session_path(session_file_path, self.settings.sessions_dir)
        LOGGER.info(
            "Connecting Telethon engagement client session_path=%s telegram_account_id=%s",
            session_path,
            _lease_account_id(self.lease),
        )
        self._client = TelegramClient(
            str(session_path),
            int(self.settings.telegram_api_id),
            self.settings.telegram_api_hash,
        )
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise EngagementAccountBanned("Telegram session is not authorized")
        LOGGER.info(
            "Connected Telethon engagement client session_path=%s telegram_account_id=%s",
            session_path,
            _lease_account_id(self.lease),
        )
        return self._client


def _classify_telethon_join_exception(exc: Exception) -> JoinResult:
    name = exc.__class__.__name__.lower()
    seconds = getattr(exc, "seconds", None)
    if "floodwait" in name or "flood_wait" in name:
        raise EngagementAccountRateLimited(int(seconds or 0), str(exc)) from exc
    if any(marker in name for marker in ("banned", "deactivated", "authkey", "sessionrevoked")):
        raise EngagementAccountBanned(str(exc)) from exc
    if "already" in name and "participant" in name:
        return JoinResult(status="already_joined", joined_at=_utcnow())
    if any(marker in name for marker in ("private", "invalid", "notoccupied", "occupied")):
        return JoinResult(status="inaccessible", joined_at=None, error_message=str(exc))
    raise TelegramEngagementError(str(exc)) from exc


def _raise_classified_telethon_send_exception(exc: Exception) -> None:
    name = exc.__class__.__name__.lower()
    message = str(exc)
    seconds = getattr(exc, "seconds", None)
    if "floodwait" in name or "flood_wait" in name:
        raise EngagementAccountRateLimited(int(seconds or 0), message) from exc
    if any(marker in name for marker in ("banned", "deactivated", "authkey", "sessionrevoked")):
        raise EngagementAccountBanned(message) from exc
    if any(
        marker in name
        for marker in (
            "chatadminrequired",
            "chatwriteforbidden",
            "forbidden",
            "invalidchannel",
            "notoccupied",
            "private",
            "userbannedinchannel",
        )
    ):
        raise EngagementCommunityInaccessible(message) from exc
    if any(marker in name for marker in ("msgid", "messagenotmodified", "reply", "messageidinvalid")):
        raise EngagementMessageNotReplyable(message) from exc
    raise TelegramEngagementError(message) from exc


def _raise_classified_telethon_account_exception(exc: Exception) -> None:
    name = exc.__class__.__name__.lower()
    message = str(exc)
    seconds = getattr(exc, "seconds", None)
    if "floodwait" in name or "flood_wait" in name:
        raise EngagementAccountRateLimited(int(seconds or 0), message) from exc
    if any(marker in name for marker in ("banned", "deactivated", "authkey", "sessionrevoked")):
        raise EngagementAccountBanned(message) from exc
    raise TelegramEngagementError(message) from exc


async def _resolve_send_entity(client: Any, community: Community) -> Any:
    target = _community_target(community)
    if target is None:
        raise EngagementCommunityInaccessible("Community has no public username or Telegram ID")

    try:
        return await client.get_entity(target)
    except ValueError as exc:
        raise EngagementCommunityInaccessible(str(exc)) from exc
    except Exception as exc:
        _raise_classified_telethon_send_exception(exc)


def _community_target(community: Community) -> str | int | None:
    username = (community.username or "").strip().lstrip("@")
    if username:
        return username
    if community.tg_id:
        return int(community.tg_id)
    return None


def _lease_account_id(lease: AccountLease | None) -> object | None:
    if lease is None:
        return None
    return lease.account_id


async def _spot_check_joined_community(client: Any, community: Community) -> None:
    target = _community_target(community)
    if target is None:
        return
    try:
        await client.get_entity(target)
    except ValueError:
        return
    except Exception as exc:
        if _is_community_access_exception(exc):
            return
        _raise_classified_telethon_account_exception(exc)


def _is_community_access_exception(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    return any(
        marker in name
        for marker in (
            "invalidchannel",
            "notoccupied",
            "private",
            "usernameinvalid",
            "usernamenotoccupied",
        )
    )


def _session_path(session_file_path: str, sessions_dir: str) -> Path:
    path = Path(session_file_path)
    if path.is_absolute():
        return path
    return Path(sessions_dir) / path


async def _mark_reply_source_read(
    client: Any,
    entity: Any,
    *,
    reply_to_tg_message_id: int,
) -> None:
    await _mark_entity_read(client, entity, max_id=reply_to_tg_message_id)


async def _mark_entity_read(client: Any, entity: Any, *, max_id: int) -> None:
    mark_read = getattr(client, "send_read_acknowledge", None)
    if not callable(mark_read):
        return
    try:
        await mark_read(entity, max_id=max_id)
    except Exception:
        return


async def _send_message_with_typing(
    client: Any,
    entity: Any,
    *,
    text: str,
    reply_to_tg_message_id: int,
    typing_delay_seconds: float,
) -> Any:
    typing_action = await _start_typing_action(client, entity)
    try:
        if typing_action is not None and typing_delay_seconds > 0:
            await asyncio.sleep(typing_delay_seconds)
        return await client.send_message(
            entity,
            text,
            reply_to=reply_to_tg_message_id,
        )
    finally:
        if typing_action is not None:
            await _stop_typing_action(typing_action)


async def _start_typing_action(client: Any, entity: Any) -> Any | None:
    action = getattr(client, "action", None)
    if not callable(action):
        return None
    try:
        typing_action = action(entity, "typing")
        await typing_action.__aenter__()
    except Exception:
        return None
    return typing_action


async def _stop_typing_action(typing_action: Any) -> None:
    try:
        await typing_action.__aexit__(None, None, None)
    except Exception:
        return


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
