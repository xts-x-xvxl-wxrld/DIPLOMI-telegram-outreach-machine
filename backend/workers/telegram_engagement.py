from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from backend.core.settings import Settings, get_settings
from backend.db.models import Community
from backend.workers.account_manager import AccountLease


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


@dataclass(frozen=True)
class JoinResult:
    status: Literal["joined", "already_joined", "inaccessible"]
    joined_at: datetime | None
    error_message: str | None = None


@dataclass(frozen=True)
class SendResult:
    sent_tg_message_id: int
    sent_at: datetime


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


class TelethonTelegramEngagementAdapter:
    def __init__(self, lease: AccountLease | None = None, *, settings: Settings | None = None) -> None:
        self.lease = lease
        self.settings = settings or get_settings()
        self._client: Any | None = None

    async def join_community(
        self,
        *,
        session_file_path: str,
        community: Community,
    ) -> JoinResult:
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

        return JoinResult(status="joined", joined_at=_utcnow())

    async def send_public_reply(
        self,
        *,
        session_file_path: str,
        community: Community,
        reply_to_tg_message_id: int,
        text: str,
    ) -> SendResult:
        client = await self._get_client(session_file_path)
        target = _community_target(community)
        if target is None:
            raise EngagementCommunityInaccessible("Community has no public username or Telegram ID")

        try:
            entity = await client.get_entity(target)
        except ValueError as exc:
            raise EngagementCommunityInaccessible(str(exc)) from exc
        except Exception as exc:
            _raise_classified_telethon_send_exception(exc)

        try:
            message = await client.send_message(
                entity,
                text,
                reply_to=reply_to_tg_message_id,
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
        return SendResult(sent_tg_message_id=int(sent_id), sent_at=sent_at)

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
        self._client = TelegramClient(
            str(session_path),
            int(self.settings.telegram_api_id),
            self.settings.telegram_api_hash,
        )
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise EngagementAccountBanned("Telegram session is not authorized")
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
    if any(marker in name for marker in ("private", "invalidchannel", "channelprivate", "notoccupied")):
        raise EngagementCommunityInaccessible(message) from exc
    if any(marker in name for marker in ("msgid", "messagenotmodified", "reply", "messageidinvalid")):
        raise EngagementMessageNotReplyable(message) from exc
    raise TelegramEngagementError(message) from exc


def _community_target(community: Community) -> str | int | None:
    username = (community.username or "").strip().lstrip("@")
    if username:
        return username
    if community.tg_id:
        return int(community.tg_id)
    return None


def _session_path(session_file_path: str, sessions_dir: str) -> Path:
    path = Path(session_file_path)
    if path.is_absolute():
        return path
    return Path(sessions_dir) / path


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
