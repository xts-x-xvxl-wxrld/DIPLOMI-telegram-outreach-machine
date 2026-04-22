from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.db.enums import (
    CollectionRunStatus,
    CommunityStatus,
    EngagementMode,
    EngagementTargetStatus,
)
from backend.db.models import (
    CollectionRun,
    Community,
    CommunityEngagementSettings,
    CommunityMember,
    CommunitySnapshot,
    EngagementTarget,
    Message,
    User,
)
from backend.services.community_collection import (
    CollectionCommunityInaccessible,
    TelegramCollectedMessage,
    TelegramCollectedUser,
    TelegramCollectionBatch,
    collect_community_engagement_messages,
)
from backend.workers.account_manager import AccountLease
from backend.workers.collection import process_collection


@pytest.mark.asyncio
async def test_collection_worker_persists_exact_batch_and_enqueues_detection() -> None:
    community_id = uuid4()
    session = CollectionSession(
        community=_community(community_id, store_messages=False),
        settings=_settings(community_id),
        target=_target(community_id),
    )
    collector = FakeCollector(
        [
            _message(101, "This CRM comparison is useful", sender_id=501),
            _message(102, "", sender_id=502),
        ]
    )
    released: list[dict[str, object]] = []
    enqueued: list[dict[str, object]] = []

    async def acquire_account(*_args: object, **_kwargs: object) -> AccountLease:
        return AccountLease(
            account_id=uuid4(),
            phone="+10000000000",
            session_file_path="session",
            lease_owner="test",
            lease_expires_at=datetime.now(timezone.utc),
        )

    async def release_account(*_args: object, **kwargs: object) -> None:
        released.append(kwargs)

    def enqueue_detect(*args: object, **kwargs: object) -> SimpleNamespace:
        enqueued.append({"args": args, "kwargs": kwargs})
        return SimpleNamespace(id="engagement.detect:exact", status="queued")

    result = await process_collection(
        {
            "community_id": str(community_id),
            "reason": "engagement",
            "requested_by": "operator",
            "window_days": 90,
        },
        session_factory=lambda: session,
        acquire_account_fn=acquire_account,
        release_account_fn=release_account,
        collector_factory=lambda _lease: collector,
        enqueue_detect_fn=enqueue_detect,
        settings=SimpleNamespace(engagement_detection_window_minutes=10),  # type: ignore[arg-type]
    )

    collection_run = session.collection_runs[0]
    assert result["status"] == CollectionRunStatus.COMPLETED.value
    assert result["messages_seen"] == 1
    assert collection_run.analysis_input["engagement_messages"][0]["tg_message_id"] == 101
    assert collection_run.analysis_input["engagement_checkpoint"]["through_tg_message_id_inclusive"] == 101
    assert session.messages == []
    assert session.users[0].tg_user_id == 501
    assert session.community_members[0].event_count == 1
    assert enqueued[0]["kwargs"]["collection_run_id"] == collection_run.id
    assert released[0]["outcome"] == "success"


@pytest.mark.asyncio
async def test_collection_service_writes_raw_messages_only_when_enabled() -> None:
    community_id = uuid4()
    session = CollectionSession(
        community=_community(community_id, store_messages=True),
        settings=_settings(community_id),
        target=_target(community_id),
    )

    summary = await collect_community_engagement_messages(
        session,  # type: ignore[arg-type]
        community_id=community_id,
        collector=FakeCollector([_message(201, "Need CRM advice", sender_id=None)]),
        reason="manual",
        window_days=30,
    )

    assert summary.messages_seen == 1
    assert len(session.messages) == 1
    assert session.messages[0].tg_message_id == 201
    assert session.collection_runs[0].analysis_input["engagement_messages"][0]["text"] == "Need CRM advice"


@pytest.mark.asyncio
async def test_collection_worker_records_inaccessible_community_without_banning_account() -> None:
    community_id = uuid4()
    session = CollectionSession(
        community=_community(community_id, store_messages=False),
        settings=_settings(community_id),
        target=_target(community_id),
    )
    released: list[dict[str, object]] = []

    async def acquire_account(*_args: object, **_kwargs: object) -> AccountLease:
        return AccountLease(
            account_id=uuid4(),
            phone="+10000000000",
            session_file_path="session",
            lease_owner="test",
            lease_expires_at=datetime.now(timezone.utc),
        )

    async def release_account(*_args: object, **kwargs: object) -> None:
        released.append(kwargs)

    result = await process_collection(
        {
            "community_id": str(community_id),
            "reason": "engagement",
            "requested_by": None,
            "window_days": 90,
        },
        session_factory=lambda: session,
        acquire_account_fn=acquire_account,
        release_account_fn=release_account,
        collector_factory=lambda _lease: FailingCollector(),
        settings=SimpleNamespace(engagement_detection_window_minutes=10),  # type: ignore[arg-type]
    )

    assert result["status"] == CollectionRunStatus.FAILED.value
    assert session.collection_runs[0].error_message == "community is private"
    assert released[0]["outcome"] == "error"


class FakeCollector:
    def __init__(self, messages: list[TelegramCollectedMessage]) -> None:
        self.messages = messages
        self.after_tg_message_id: int | None = None

    async def collect_messages(
        self,
        _community: Community,
        *,
        after_tg_message_id: int | None,
        limit: int,
    ) -> TelegramCollectionBatch:
        self.after_tg_message_id = after_tg_message_id
        return TelegramCollectionBatch(messages=self.messages[:limit])


class FailingCollector:
    async def collect_messages(self, *_args: object, **_kwargs: object) -> TelegramCollectionBatch:
        raise CollectionCommunityInaccessible("community is private")


class CollectionSession:
    def __init__(
        self,
        *,
        community: Community,
        settings: CommunityEngagementSettings,
        target: EngagementTarget | None,
        previous_runs: list[CollectionRun] | None = None,
    ) -> None:
        self.community = community
        self.settings = settings
        self.target = target
        self.previous_runs = previous_runs or []
        self.collection_runs: list[CollectionRun] = []
        self.snapshots: list[CommunitySnapshot] = []
        self.messages: list[Message] = []
        self.users: list[User] = []
        self.community_members: list[CommunityMember] = []
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "CollectionSession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def get(self, model: object, item_id: object) -> object | None:
        if model is Community and item_id == self.community.id:
            return self.community
        return None

    async def scalar(self, statement: object) -> object | None:
        entity = statement.column_descriptions[0]["entity"]  # type: ignore[attr-defined]
        if entity is CommunityEngagementSettings:
            return self.settings
        if entity is EngagementTarget:
            return self.target
        if entity in {User, CommunityMember, Message}:
            return None
        return None

    async def scalars(self, statement: object) -> list[object]:
        entity = statement.column_descriptions[0]["entity"]  # type: ignore[attr-defined]
        if entity is CollectionRun:
            return self.previous_runs
        return []

    def add(self, model: object) -> None:
        if isinstance(model, CollectionRun):
            self.collection_runs.append(model)
        elif isinstance(model, CommunitySnapshot):
            self.snapshots.append(model)
        elif isinstance(model, Message):
            self.messages.append(model)
        elif isinstance(model, User):
            self.users.append(model)
        elif isinstance(model, CommunityMember):
            self.community_members.append(model)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _community(community_id: object, *, store_messages: bool) -> Community:
    return Community(
        id=community_id,
        tg_id=100,
        username="example",
        title="Example Group",
        is_group=True,
        status=CommunityStatus.MONITORING.value,
        store_messages=store_messages,
    )


def _settings(community_id: object) -> CommunityEngagementSettings:
    return CommunityEngagementSettings(
        id=uuid4(),
        community_id=community_id,
        mode=EngagementMode.SUGGEST.value,
        allow_join=False,
        allow_post=False,
        reply_only=True,
        require_approval=True,
        max_posts_per_day=1,
        min_minutes_between_posts=240,
    )


def _target(community_id: object) -> EngagementTarget:
    return EngagementTarget(
        id=uuid4(),
        community_id=community_id,
        submitted_ref="example",
        status=EngagementTargetStatus.APPROVED.value,
        allow_detect=True,
        added_by="operator",
    )


def _message(message_id: int, text: str, *, sender_id: int | None) -> TelegramCollectedMessage:
    sender = (
        TelegramCollectedUser(tg_user_id=sender_id, username=f"user{sender_id}")
        if sender_id is not None
        else None
    )
    return TelegramCollectedMessage(
        tg_message_id=message_id,
        text=text,
        message_date=datetime.now(timezone.utc),
        sender=sender,
        is_replyable=True,
    )
