from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.db.enums import (
    CommunityAccountMembershipStatus,
    CommunityStatus,
    EngagementActionStatus,
    EngagementMode,
    EngagementTargetStatus,
)
from backend.db.models import Community, CommunityAccountMembership, CommunityEngagementSettings, EngagementTarget
from backend.workers.account_manager import AccountLease
from backend.workers.community_join import process_community_join
from backend.workers.telegram_engagement import (
    EngagementAccountBanned,
    EngagementAccountRateLimited,
    JoinResult,
)


@pytest.mark.asyncio
async def test_community_join_skips_when_join_not_allowed() -> None:
    community_id = uuid4()
    session = FakeSession(
        community=Community(
            id=community_id,
            tg_id=100,
            username="example",
            status=CommunityStatus.APPROVED.value,
        ),
        settings=CommunityEngagementSettings(
            id=uuid4(),
            community_id=community_id,
            mode=EngagementMode.SUGGEST.value,
            allow_join=False,
            allow_post=False,
            reply_only=True,
            require_approval=True,
            max_posts_per_day=1,
            min_minutes_between_posts=240,
        ),
    )
    acquire_called = False

    async def fake_acquire(*args: object, **kwargs: object) -> AccountLease:
        nonlocal acquire_called
        acquire_called = True
        raise AssertionError("account acquisition should not run")

    result = await process_community_join(
        {"community_id": str(community_id), "telegram_account_id": None, "requested_by": "op"},
        session_factory=lambda: session,
        acquire_account_fn=fake_acquire,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "join_not_allowed"
    assert acquire_called is False
    assert session.added == []


@pytest.mark.asyncio
async def test_community_join_records_success_and_releases_account() -> None:
    community_id = uuid4()
    account_id = uuid4()
    joined_at = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
    session = _joinable_session(community_id)
    releases: list[dict[str, object]] = []
    adapter = FakeAdapter(result=JoinResult(status="joined", joined_at=joined_at))
    detect_calls: list[dict[str, object]] = []

    result = await process_community_join(
        {"community_id": str(community_id), "telegram_account_id": None, "requested_by": "op"},
        session_factory=lambda: session,
        acquire_account_fn=_fake_acquire(account_id),
        release_account_fn=_capture_release(releases),
        adapter_factory=lambda lease: adapter,
        enqueue_detect_fn=_capture_detect(detect_calls),
    )

    assert result["status"] == "processed"
    assert result["action_status"] == "sent"
    assert session.membership is not None
    assert session.membership.status == CommunityAccountMembershipStatus.JOINED.value
    assert session.membership.joined_at == joined_at
    assert session.action is not None
    assert session.action.status == EngagementActionStatus.SENT.value
    assert session.action.action_type == "join"
    assert adapter.calls == [
        {"session_file_path": "session", "community_id": community_id},
    ]
    assert adapter.closed is True
    assert releases[0]["outcome"] == "success"
    assert releases[0]["account_id"] == account_id
    assert detect_calls == [
        {
            "community_id": community_id,
            "window_minutes": 60,
            "requested_by": "op",
        }
    ]


@pytest.mark.asyncio
async def test_community_join_skips_without_approved_engagement_target() -> None:
    community_id = uuid4()
    session = _joinable_session(community_id, target=None)
    acquire_called = False

    async def fake_acquire(*args: object, **kwargs: object) -> AccountLease:
        nonlocal acquire_called
        acquire_called = True
        raise AssertionError("account acquisition should not run")

    result = await process_community_join(
        {"community_id": str(community_id), "telegram_account_id": None, "requested_by": "op"},
        session_factory=lambda: session,
        acquire_account_fn=fake_acquire,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "engagement_target_join_not_approved"
    assert acquire_called is False
    assert session.action is None


@pytest.mark.asyncio
async def test_community_join_uses_existing_joined_membership_and_confirms_already_joined() -> None:
    community_id = uuid4()
    account_id = uuid4()
    session = _joinable_session(
        community_id,
        membership=CommunityAccountMembership(
            id=uuid4(),
            community_id=community_id,
            telegram_account_id=account_id,
            status=CommunityAccountMembershipStatus.JOINED.value,
            joined_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        ),
    )
    acquired_by_id: list[object] = []
    adapter = FakeAdapter(result=JoinResult(status="already_joined", joined_at=None))
    detect_calls: list[dict[str, object]] = []

    async def fake_acquire_by_id(session_arg: FakeSession, **kwargs: object) -> AccountLease:
        acquired_by_id.append(kwargs["account_id"])
        return _lease(account_id, job_id=str(kwargs["job_id"]))

    result = await process_community_join(
        {"community_id": str(community_id), "telegram_account_id": None, "requested_by": "op"},
        session_factory=lambda: session,
        acquire_account_fn=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generic acquisition should not run")
        ),
        acquire_account_by_id_fn=fake_acquire_by_id,
        release_account_fn=_capture_release([]),
        adapter_factory=lambda lease: adapter,
        enqueue_detect_fn=_capture_detect(detect_calls),
    )

    assert result["status"] == "processed"
    assert acquired_by_id == [account_id]
    assert session.membership is not None
    assert session.membership.status == CommunityAccountMembershipStatus.JOINED.value
    assert session.action is not None
    assert session.action.status == EngagementActionStatus.SENT.value
    assert detect_calls == [
        {
            "community_id": community_id,
            "window_minutes": 60,
            "requested_by": "op",
        }
    ]


@pytest.mark.asyncio
async def test_community_join_marks_inaccessible_as_skipped_without_account_penalty() -> None:
    community_id = uuid4()
    account_id = uuid4()
    session = _joinable_session(community_id)
    releases: list[dict[str, object]] = []
    adapter = FakeAdapter(
        result=JoinResult(
            status="inaccessible",
            joined_at=None,
            error_message="private community",
        )
    )

    result = await process_community_join(
        {"community_id": str(community_id), "telegram_account_id": None, "requested_by": "op"},
        session_factory=lambda: session,
        acquire_account_fn=_fake_acquire(account_id),
        release_account_fn=_capture_release(releases),
        adapter_factory=lambda lease: adapter,
    )

    assert result["status"] == "skipped"
    assert session.membership is not None
    assert session.membership.status == CommunityAccountMembershipStatus.FAILED.value
    assert session.membership.last_error == "private community"
    assert session.action is not None
    assert session.action.status == EngagementActionStatus.SKIPPED.value
    assert releases[0]["outcome"] == "success"


@pytest.mark.asyncio
async def test_community_join_maps_flood_wait_to_rate_limited_release() -> None:
    community_id = uuid4()
    account_id = uuid4()
    session = _joinable_session(community_id)
    releases: list[dict[str, object]] = []
    adapter = FakeAdapter(exc=EngagementAccountRateLimited(120, "flood wait"))

    with pytest.raises(EngagementAccountRateLimited):
        await process_community_join(
            {"community_id": str(community_id), "telegram_account_id": None, "requested_by": "op"},
            session_factory=lambda: session,
            acquire_account_fn=_fake_acquire(account_id),
            release_account_fn=_capture_release(releases),
            adapter_factory=lambda lease: adapter,
        )

    assert session.rollbacks == 1
    assert session.membership is not None
    assert session.membership.status == CommunityAccountMembershipStatus.FAILED.value
    assert session.action is not None
    assert session.action.status == EngagementActionStatus.FAILED.value
    assert releases[0]["outcome"] == "rate_limited"
    assert releases[0]["flood_wait_seconds"] == 120


@pytest.mark.asyncio
async def test_community_join_maps_banned_session_to_banned_membership_and_release() -> None:
    community_id = uuid4()
    account_id = uuid4()
    session = _joinable_session(community_id)
    releases: list[dict[str, object]] = []
    adapter = FakeAdapter(exc=EngagementAccountBanned("session revoked"))

    with pytest.raises(EngagementAccountBanned):
        await process_community_join(
            {"community_id": str(community_id), "telegram_account_id": None, "requested_by": "op"},
            session_factory=lambda: session,
            acquire_account_fn=_fake_acquire(account_id),
            release_account_fn=_capture_release(releases),
            adapter_factory=lambda lease: adapter,
        )

    assert session.membership is not None
    assert session.membership.status == CommunityAccountMembershipStatus.BANNED.value
    assert session.action is not None
    assert session.action.status == EngagementActionStatus.FAILED.value
    assert releases[0]["outcome"] == "banned"


class FakeSession:
    def __init__(
        self,
        *,
        community: Community,
        settings: CommunityEngagementSettings,
        target: EngagementTarget | None = None,
        membership: CommunityAccountMembership | None = None,
    ) -> None:
        self.community = community
        self.settings = settings
        self.target = target
        self.membership = membership
        self.action = None
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    async def __aenter__(self) -> FakeSession:
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
        if entity is CommunityAccountMembership:
            return self.membership
        return None

    def add(self, model: object) -> None:
        self.added.append(model)
        if isinstance(model, CommunityAccountMembership):
            self.membership = model
        else:
            self.action = model

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeAdapter:
    def __init__(
        self,
        *,
        result: JoinResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.result = result
        self.exc = exc
        self.calls: list[dict[str, object]] = []
        self.closed = False

    async def join_community(self, *, session_file_path: str, community: Community) -> JoinResult:
        self.calls.append({"session_file_path": session_file_path, "community_id": community.id})
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result

    async def aclose(self) -> None:
        self.closed = True


def _joinable_session(
    community_id: object,
    *,
    membership: CommunityAccountMembership | None = None,
    target: EngagementTarget | None | bool = True,
) -> FakeSession:
    engagement_target = _target(community_id) if target is True else target
    return FakeSession(
        community=Community(
            id=community_id,
            tg_id=100,
            username="example",
            status=CommunityStatus.APPROVED.value,
        ),
        settings=CommunityEngagementSettings(
            id=uuid4(),
            community_id=community_id,
            mode=EngagementMode.SUGGEST.value,
            allow_join=True,
            allow_post=False,
            reply_only=True,
            require_approval=True,
            max_posts_per_day=1,
            min_minutes_between_posts=240,
        ),
        target=engagement_target,
        membership=membership,
    )


def _fake_acquire(account_id: object):
    async def fake_acquire(session_arg: FakeSession, *, job_id: str, purpose: str) -> AccountLease:
        assert purpose == "engagement_join"
        return _lease(account_id, job_id=job_id)

    return fake_acquire


def _capture_release(calls: list[dict[str, object]]):
    async def fake_release(session_arg: FakeSession, **kwargs: object) -> None:
        calls.append(kwargs)

    return fake_release


def _capture_detect(calls: list[dict[str, object]]):
    def fake_detect(community_id: object, *, window_minutes: int, requested_by: str) -> None:
        calls.append(
            {
                "community_id": community_id,
                "window_minutes": window_minutes,
                "requested_by": requested_by,
            }
        )

    return fake_detect


def _lease(account_id: object, *, job_id: str) -> AccountLease:
    return AccountLease(
        account_id=account_id,
        phone="+123456789",
        session_file_path="session",
        lease_owner=job_id,
        lease_expires_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
    )


def _target(community_id: object) -> EngagementTarget:
    return EngagementTarget(
        id=uuid4(),
        community_id=community_id,
        submitted_ref=str(community_id),
        submitted_ref_type="community_id",
        status=EngagementTargetStatus.APPROVED.value,
        allow_join=True,
        allow_detect=True,
        allow_post=True,
        added_by="op",
    )
