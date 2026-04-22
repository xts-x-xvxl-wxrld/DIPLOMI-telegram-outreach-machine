from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from backend.db.enums import (
    CommunityAccountMembershipStatus,
    CommunityStatus,
    EngagementActionStatus,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementTargetStatus,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementAction,
    EngagementCandidate,
    EngagementTarget,
    EngagementTopic,
)
from backend.workers.account_manager import AccountLease
from backend.workers.engagement_send import SendLimitDecision, process_engagement_send
from backend.workers.telegram_engagement import (
    EngagementAccountRateLimited,
    EngagementMessageNotReplyable,
    SendResult,
)

_FIXTURE_NOW = datetime.now(timezone.utc).replace(microsecond=0)


@pytest.mark.asyncio
async def test_engagement_send_skips_without_approval() -> None:
    community = _community()
    candidate = _candidate(community, status=EngagementCandidateStatus.NEEDS_REVIEW.value)
    session = _send_session(community=community, candidate=candidate)
    acquire_called = False

    async def fake_acquire(*args: object, **kwargs: object) -> AccountLease:
        nonlocal acquire_called
        acquire_called = True
        raise AssertionError("account acquisition should not run")

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=fake_acquire,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "candidate_not_approved"
    assert acquire_called is False
    assert session.action is None


@pytest.mark.asyncio
async def test_engagement_send_skips_when_settings_are_missing_or_disabled() -> None:
    community = _community()
    account_id = uuid4()
    candidate = _candidate(community)
    session = FakeSession(
        community=community,
        settings=None,
        candidate=candidate,
        membership=_membership(community.id, account_id),
    )
    acquire_called = False

    async def fake_acquire(*args: object, **kwargs: object) -> AccountLease:
        nonlocal acquire_called
        acquire_called = True
        raise AssertionError("account acquisition should not run")

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=fake_acquire,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "posting_not_allowed"
    assert acquire_called is False
    assert session.action is None


@pytest.mark.asyncio
async def test_engagement_send_skips_without_approved_engagement_target() -> None:
    community = _community()
    account_id = uuid4()
    candidate = _candidate(community)
    session = _send_session(
        community=community,
        candidate=candidate,
        membership=_membership(community.id, account_id),
        target=None,
    )
    acquire_called = False

    async def fake_acquire(*args: object, **kwargs: object) -> AccountLease:
        nonlocal acquire_called
        acquire_called = True
        raise AssertionError("account acquisition should not run")

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=fake_acquire,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "engagement_target_post_not_approved"
    assert acquire_called is False
    assert session.action is None


@pytest.mark.asyncio
async def test_engagement_send_expires_stale_candidate_without_network_call() -> None:
    community = _community()
    account_id = uuid4()
    candidate = _candidate(community)
    candidate.expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    session = _send_session(
        community=community,
        candidate=candidate,
        membership=_membership(community.id, account_id),
    )
    adapter = FakeSendAdapter(result=SendResult(sent_tg_message_id=456, sent_at=_now()))

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("account acquisition should not run")
        ),
        adapter_factory=lambda lease: adapter,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "candidate_expired"
    assert candidate.status == EngagementCandidateStatus.EXPIRED.value
    assert session.action is None
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_engagement_send_skips_stale_candidate_by_reply_deadline() -> None:
    community = _community()
    account_id = uuid4()
    candidate = _candidate(community)
    candidate.reply_deadline_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    session = _send_session(
        community=community,
        candidate=candidate,
        membership=_membership(community.id, account_id),
    )

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("account acquisition should not run")
        ),
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "candidate_stale"
    assert candidate.status == EngagementCandidateStatus.EXPIRED.value
    assert session.action is None


@pytest.mark.asyncio
async def test_engagement_send_skips_without_joined_membership() -> None:
    community = _community()
    candidate = _candidate(community)
    session = _send_session(community=community, candidate=candidate, membership=None)
    acquire_called = False

    async def fake_acquire(*args: object, **kwargs: object) -> AccountLease:
        nonlocal acquire_called
        acquire_called = True
        raise AssertionError("account acquisition should not run")

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=fake_acquire,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "no_joined_membership"
    assert acquire_called is False
    assert session.action is None


@pytest.mark.asyncio
async def test_engagement_send_records_success_and_releases_account() -> None:
    community = _community()
    account_id = uuid4()
    candidate = _candidate(community)
    membership = _membership(community.id, account_id)
    session = _send_session(community=community, candidate=candidate, membership=membership)
    releases: list[dict[str, object]] = []
    sent_at = _now() + timedelta(minutes=30)
    adapter = FakeSendAdapter(result=SendResult(sent_tg_message_id=456, sent_at=sent_at))

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=_fake_acquire(account_id),
        release_account_fn=_capture_release(releases),
        adapter_factory=lambda lease: adapter,
        rate_limit_checker=_allow_send,
    )

    assert result["status"] == "processed"
    assert result["action_status"] == EngagementActionStatus.SENT.value
    assert candidate.status == EngagementCandidateStatus.SENT.value
    assert session.action is not None
    assert session.action.outbound_text == "Compare ownership and integrations first."
    assert session.action.reply_to_tg_message_id == 123
    assert session.action.sent_tg_message_id == 456
    assert session.action.sent_at == sent_at
    assert adapter.calls == [
        {
            "session_file_path": "session",
            "community_id": community.id,
            "reply_to_tg_message_id": 123,
            "text": "Compare ownership and integrations first.",
        }
    ]
    assert adapter.closed is True
    assert releases[0]["outcome"] == "success"
    assert releases[0]["account_id"] == account_id


@pytest.mark.asyncio
async def test_engagement_send_rate_limit_skip_creates_audit_without_network_call() -> None:
    community = _community()
    account_id = uuid4()
    candidate = _candidate(community)
    membership = _membership(community.id, account_id)
    session = _send_session(community=community, candidate=candidate, membership=membership)
    adapter = FakeSendAdapter(result=SendResult(sent_tg_message_id=456, sent_at=_now()))
    acquire_called = False

    async def fake_acquire(*args: object, **kwargs: object) -> AccountLease:
        nonlocal acquire_called
        acquire_called = True
        raise AssertionError("account acquisition should not run when limits block")

    async def block_send(*args: object, **kwargs: object) -> SendLimitDecision:
        return SendLimitDecision(False, "Community daily send limit reached")

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=fake_acquire,
        adapter_factory=lambda lease: adapter,
        rate_limit_checker=block_send,
    )

    assert result["status"] == "skipped"
    assert result["action_status"] == EngagementActionStatus.SKIPPED.value
    assert result["reason"] == "Community daily send limit reached"
    assert candidate.status == EngagementCandidateStatus.APPROVED.value
    assert session.action is not None
    assert session.action.status == EngagementActionStatus.SKIPPED.value
    assert adapter.calls == []
    assert acquire_called is False


@pytest.mark.asyncio
async def test_engagement_send_idempotent_retry_marks_candidate_sent_without_duplicate_send() -> None:
    community = _community()
    account_id = uuid4()
    candidate = _candidate(community)
    existing_action = _action(candidate, account_id, status=EngagementActionStatus.SENT.value)
    existing_action.sent_tg_message_id = 789
    session = _send_session(
        community=community,
        candidate=candidate,
        membership=_membership(community.id, account_id),
        action=existing_action,
    )
    adapter = FakeSendAdapter(result=SendResult(sent_tg_message_id=456, sent_at=_now()))

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("account acquisition should not run")
        ),
        adapter_factory=lambda lease: adapter,
    )

    assert result["status"] == "processed"
    assert result["action_status"] == EngagementActionStatus.SENT.value
    assert result["sent_tg_message_id"] == 789
    assert candidate.status == EngagementCandidateStatus.SENT.value
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_engagement_send_existing_queued_action_fails_closed() -> None:
    community = _community()
    account_id = uuid4()
    candidate = _candidate(community)
    existing_action = _action(candidate, account_id, status=EngagementActionStatus.QUEUED.value)
    session = _send_session(
        community=community,
        candidate=candidate,
        membership=_membership(community.id, account_id),
        action=existing_action,
    )
    adapter = FakeSendAdapter(result=SendResult(sent_tg_message_id=456, sent_at=_now()))

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("account acquisition should not run")
        ),
        adapter_factory=lambda lease: adapter,
        rate_limit_checker=_allow_send,
    )

    assert result["status"] == "failed"
    assert existing_action.status == EngagementActionStatus.FAILED.value
    assert "cannot be safely retried" in (existing_action.error_message or "")
    assert candidate.status == EngagementCandidateStatus.APPROVED.value
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_engagement_send_maps_flood_wait_to_rate_limited_release() -> None:
    community = _community()
    account_id = uuid4()
    candidate = _candidate(community)
    membership = _membership(community.id, account_id)
    session = _send_session(community=community, candidate=candidate, membership=membership)
    releases: list[dict[str, object]] = []
    adapter = FakeSendAdapter(exc=EngagementAccountRateLimited(120, "flood wait"))

    with pytest.raises(EngagementAccountRateLimited):
        await process_engagement_send(
            {"candidate_id": str(candidate.id), "approved_by": "op"},
            session_factory=lambda: session,
            acquire_account_by_id_fn=_fake_acquire(account_id),
            release_account_fn=_capture_release(releases),
            adapter_factory=lambda lease: adapter,
            rate_limit_checker=_allow_send,
        )

    assert session.rollbacks == 1
    assert session.action is not None
    assert session.action.status == EngagementActionStatus.FAILED.value
    assert candidate.status == EngagementCandidateStatus.APPROVED.value
    assert releases[0]["outcome"] == "rate_limited"
    assert releases[0]["flood_wait_seconds"] == 120


@pytest.mark.asyncio
async def test_engagement_send_message_not_replyable_expires_candidate_without_account_penalty() -> None:
    community = _community()
    account_id = uuid4()
    candidate = _candidate(community)
    membership = _membership(community.id, account_id)
    session = _send_session(community=community, candidate=candidate, membership=membership)
    releases: list[dict[str, object]] = []
    adapter = FakeSendAdapter(exc=EngagementMessageNotReplyable("message no longer replyable"))

    result = await process_engagement_send(
        {"candidate_id": str(candidate.id), "approved_by": "op"},
        session_factory=lambda: session,
        acquire_account_by_id_fn=_fake_acquire(account_id),
        release_account_fn=_capture_release(releases),
        adapter_factory=lambda lease: adapter,
        rate_limit_checker=_allow_send,
    )

    assert result["status"] == "skipped"
    assert session.action is not None
    assert session.action.status == EngagementActionStatus.SKIPPED.value
    assert candidate.status == EngagementCandidateStatus.EXPIRED.value
    assert releases[0]["outcome"] == "success"


class FakeSession:
    def __init__(
        self,
        *,
        community: Community,
        settings: CommunityEngagementSettings | None,
        candidate: EngagementCandidate,
        target: EngagementTarget | None | bool = True,
        membership: CommunityAccountMembership | None = None,
        action: EngagementAction | None = None,
    ) -> None:
        self.community = community
        self.settings = settings
        self.candidate = candidate
        self.target = _target(community.id) if target is True else target
        self.membership = membership
        self.action = action
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
        if entity is EngagementCandidate:
            return self.candidate
        if entity is EngagementAction:
            return self.action
        if entity is CommunityEngagementSettings:
            return self.settings
        if entity is EngagementTarget:
            return self.target
        if entity is CommunityAccountMembership:
            return self.membership
        return None

    def add(self, model: object) -> None:
        self.added.append(model)
        if isinstance(model, EngagementAction):
            self.action = model

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeSendAdapter:
    def __init__(
        self,
        *,
        result: SendResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.result = result
        self.exc = exc
        self.calls: list[dict[str, object]] = []
        self.closed = False

    async def send_public_reply(
        self,
        *,
        session_file_path: str,
        community: Community,
        reply_to_tg_message_id: int,
        text: str,
    ) -> SendResult:
        self.calls.append(
            {
                "session_file_path": session_file_path,
                "community_id": community.id,
                "reply_to_tg_message_id": reply_to_tg_message_id,
                "text": text,
            }
        )
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result

    async def aclose(self) -> None:
        self.closed = True


async def _allow_send(*args: object, **kwargs: object) -> SendLimitDecision:
    return SendLimitDecision(True)


def _send_session(
    *,
    community: Community,
    candidate: EngagementCandidate,
    membership: CommunityAccountMembership | None = None,
    action: EngagementAction | None = None,
    allow_post: bool = True,
    target: EngagementTarget | None | bool = True,
) -> FakeSession:
    return FakeSession(
        community=community,
        candidate=candidate,
        membership=membership,
        action=action,
        target=target,
        settings=CommunityEngagementSettings(
            id=uuid4(),
            community_id=community.id,
            mode=EngagementMode.SUGGEST.value,
            allow_join=True,
            allow_post=allow_post,
            reply_only=True,
            require_approval=True,
            max_posts_per_day=1,
            min_minutes_between_posts=240,
        ),
    )


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


def _candidate(
    community: Community,
    *,
    status: str = EngagementCandidateStatus.APPROVED.value,
) -> EngagementCandidate:
    topic = EngagementTopic(
        id=uuid4(),
        name="CRM",
        stance_guidance="Be useful.",
        trigger_keywords=["crm"],
        negative_keywords=[],
        example_good_replies=[],
        example_bad_replies=[],
        active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    candidate = EngagementCandidate(
        id=uuid4(),
        community_id=community.id,
        topic_id=topic.id,
        source_tg_message_id=123,
        source_excerpt="The group is comparing CRM tools.",
        source_message_date=_now() - timedelta(minutes=30),
        detected_at=_now(),
        detected_reason="The group is comparing CRM tools.",
        moment_strength="good",
        timeliness="fresh",
        reply_value="practical_tip",
        suggested_reply="Compare ownership and integrations first.",
        final_reply="Compare ownership and integrations first." if status == EngagementCandidateStatus.APPROVED.value else None,
        risk_notes=[],
        status=status,
        reviewed_by="op",
        reviewed_at=_now(),
        review_deadline_at=_now() + timedelta(minutes=30),
        reply_deadline_at=_now() + timedelta(minutes=60),
        expires_at=datetime(2999, 4, 20, tzinfo=timezone.utc),
        created_at=_now(),
        updated_at=_now(),
    )
    candidate.community = community
    candidate.topic = topic
    return candidate


def _membership(community_id: object, account_id: object) -> CommunityAccountMembership:
    return CommunityAccountMembership(
        id=uuid4(),
        community_id=community_id,
        telegram_account_id=account_id,
        status=CommunityAccountMembershipStatus.JOINED.value,
        joined_at=_now() - timedelta(days=1),
    )


def _action(
    candidate: EngagementCandidate,
    account_id: object,
    *,
    status: str,
) -> EngagementAction:
    return EngagementAction(
        id=uuid4(),
        candidate_id=candidate.id,
        community_id=candidate.community_id,
        telegram_account_id=account_id,
        action_type="reply",
        status=status,
        idempotency_key=f"engagement.send:{candidate.id}",
        outbound_text=candidate.final_reply,
        reply_to_tg_message_id=candidate.source_tg_message_id,
        scheduled_at=_now(),
        created_at=_now(),
        updated_at=_now(),
    )


def _fake_acquire(account_id: object):
    async def fake_acquire(session_arg: FakeSession, *, account_id: object, job_id: str, purpose: str) -> AccountLease:
        assert purpose == "engagement_send"
        return _lease(account_id, job_id=job_id)

    return fake_acquire


def _capture_release(calls: list[dict[str, object]]):
    async def fake_release(session_arg: FakeSession, **kwargs: object) -> None:
        calls.append(kwargs)

    return fake_release


def _lease(account_id: object, *, job_id: str) -> AccountLease:
    return AccountLease(
        account_id=account_id,
        phone="+123456789",
        session_file_path="session",
        lease_owner=job_id,
        lease_expires_at=_now() + timedelta(hours=1),
    )


def _now() -> datetime:
    return _FIXTURE_NOW


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
