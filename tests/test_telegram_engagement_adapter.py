from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.db.enums import CommunityStatus
from backend.db.models import Community
from backend.workers.telegram_engagement import (
    EngagementAccountBanned,
    EngagementMessageNotReplyable,
    TelethonTelegramEngagementAdapter,
)


@pytest.mark.asyncio
async def test_send_public_reply_marks_source_read_and_types_before_sending() -> None:
    community = _community()
    client = FakeTelethonClient()
    adapter = TelethonTelegramEngagementAdapter(typing_delay_seconds=0.0)
    adapter._client = client

    result = await adapter.send_public_reply(
        session_file_path="session",
        community=community,
        reply_to_tg_message_id=123,
        text="Compare ownership and integrations first.",
    )

    assert result.sent_tg_message_id == 456
    assert client.read_calls == [{"entity": "example-entity", "max_id": 123}]
    assert client.typing_entries == ["example-entity"]
    assert client.typing_exits == ["example-entity"]
    assert client.send_calls == [
        {
            "entity": "example-entity",
            "text": "Compare ownership and integrations first.",
            "reply_to": 123,
        }
    ]


@pytest.mark.asyncio
async def test_send_public_reply_still_sends_when_presence_calls_fail() -> None:
    community = _community()
    client = FakeTelethonClient(read_error=RuntimeError("read failed"), typing_error=RuntimeError("typing failed"))
    adapter = TelethonTelegramEngagementAdapter(typing_delay_seconds=0.0)
    adapter._client = client

    result = await adapter.send_public_reply(
        session_file_path="session",
        community=community,
        reply_to_tg_message_id=123,
        text="Compare ownership and integrations first.",
    )

    assert result.sent_tg_message_id == 456
    assert client.send_calls == [
        {
            "entity": "example-entity",
            "text": "Compare ownership and integrations first.",
            "reply_to": 123,
        }
    ]


@pytest.mark.asyncio
async def test_verify_reply_source_accepts_accessible_source_message() -> None:
    community = _community()
    client = FakeTelethonClient()
    adapter = TelethonTelegramEngagementAdapter(typing_delay_seconds=0.0)
    adapter._client = client

    result = await adapter.verify_reply_source(
        session_file_path="session",
        community=community,
        reply_to_tg_message_id=123,
    )

    assert result.source_tg_message_id == 123
    assert client.message_lookup_calls == [{"entity": "example-entity", "ids": 123}]
    assert client.send_calls == []


@pytest.mark.asyncio
async def test_verify_reply_source_rejects_missing_source_message() -> None:
    community = _community()
    client = FakeTelethonClient(source_message=None)
    adapter = TelethonTelegramEngagementAdapter(typing_delay_seconds=0.0)
    adapter._client = client

    with pytest.raises(EngagementMessageNotReplyable, match="no longer accessible"):
        await adapter.verify_reply_source(
            session_file_path="session",
            community=community,
            reply_to_tg_message_id=123,
        )

    assert client.send_calls == []


@pytest.mark.asyncio
async def test_verify_reply_source_rejects_non_replyable_service_message() -> None:
    community = _community()
    client = FakeTelethonClient(source_message=FakeTelegramMessage(id=123, action=object()))
    adapter = TelethonTelegramEngagementAdapter(typing_delay_seconds=0.0)
    adapter._client = client

    with pytest.raises(EngagementMessageNotReplyable, match="not replyable"):
        await adapter.verify_reply_source(
            session_file_path="session",
            community=community,
            reply_to_tg_message_id=123,
        )


@pytest.mark.asyncio
async def test_read_recent_messages_after_join_marks_latest_visible_message_read() -> None:
    community = _community()
    client = FakeTelethonClient(recent_messages=[FakeTelegramMessage(id=10), FakeTelegramMessage(id=12)])
    adapter = TelethonTelegramEngagementAdapter(typing_delay_seconds=0.0)
    adapter._client = client

    count = await adapter.read_recent_messages_after_join(
        session_file_path="session",
        community=community,
        limit=5,
    )

    assert count == 2
    assert client.iter_calls == [{"entity": "example-entity", "limit": 5}]
    assert client.read_calls == [{"entity": "example-entity", "max_id": 12}]


@pytest.mark.asyncio
async def test_check_account_health_requires_authorized_identity() -> None:
    client = FakeTelethonClient(identity=None)
    adapter = TelethonTelegramEngagementAdapter(typing_delay_seconds=0.0)
    adapter._client = client

    with pytest.raises(EngagementAccountBanned, match="no account identity"):
        await adapter.check_account_health(session_file_path="session")


@pytest.mark.asyncio
async def test_check_account_health_spot_checks_joined_communities() -> None:
    community = _community()
    client = FakeTelethonClient()
    adapter = TelethonTelegramEngagementAdapter(typing_delay_seconds=0.0)
    adapter._client = client

    await adapter.check_account_health(
        session_file_path="session",
        joined_communities=[community],
    )

    assert client.get_me_calls == 1
    assert client.entity_lookup_calls == ["example"]


class FakeTelegramMessage:
    date = datetime(2026, 4, 30, tzinfo=timezone.utc)

    def __init__(self, *, id: int = 456, action: object | None = None) -> None:
        self.id = id
        self.action = action


class FakeTypingAction:
    def __init__(
        self,
        client: FakeTelethonClient,
        entity: object,
        error: Exception | None,
    ) -> None:
        self.client = client
        self.entity = entity
        self.error = error

    async def __aenter__(self) -> None:
        if self.error is not None:
            raise self.error
        self.client.typing_entries.append(self.entity)

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.client.typing_exits.append(self.entity)


class FakeTelethonClient:
    def __init__(
        self,
        *,
        read_error: Exception | None = None,
        typing_error: Exception | None = None,
        source_message: FakeTelegramMessage | None = FakeTelegramMessage(id=123),
        recent_messages: list[FakeTelegramMessage] | None = None,
        identity: object | None = object(),
    ) -> None:
        self.read_error = read_error
        self.typing_error = typing_error
        self.source_message = source_message
        self.recent_messages = recent_messages or []
        self.identity = identity
        self.get_me_calls = 0
        self.entity_lookup_calls: list[object] = []
        self.read_calls: list[dict[str, object]] = []
        self.iter_calls: list[dict[str, object]] = []
        self.message_lookup_calls: list[dict[str, object]] = []
        self.send_calls: list[dict[str, object]] = []
        self.typing_entries: list[object] = []
        self.typing_exits: list[object] = []

    async def get_entity(self, target: object) -> str:
        assert target == "example"
        self.entity_lookup_calls.append(target)
        return "example-entity"

    async def get_me(self) -> object | None:
        self.get_me_calls += 1
        return self.identity

    async def send_read_acknowledge(self, entity: object, *, max_id: int) -> None:
        if self.read_error is not None:
            raise self.read_error
        self.read_calls.append({"entity": entity, "max_id": max_id})

    async def get_messages(self, entity: object, *, ids: int) -> FakeTelegramMessage | None:
        self.message_lookup_calls.append({"entity": entity, "ids": ids})
        return self.source_message

    async def iter_messages(self, entity: object, *, limit: int):
        self.iter_calls.append({"entity": entity, "limit": limit})
        for message in self.recent_messages[:limit]:
            yield message

    def action(self, entity: object, action_name: str) -> FakeTypingAction:
        assert action_name == "typing"
        return FakeTypingAction(self, entity, self.typing_error)

    async def send_message(
        self,
        entity: object,
        text: str,
        *,
        reply_to: int,
    ) -> FakeTelegramMessage:
        self.send_calls.append({"entity": entity, "text": text, "reply_to": reply_to})
        return FakeTelegramMessage(id=456)


def _community() -> Community:
    return Community(
        id=uuid4(),
        tg_id=100,
        username="example",
        title="Example Group",
        is_group=True,
        status=CommunityStatus.MONITORING.value,
        store_messages=False,
    )
