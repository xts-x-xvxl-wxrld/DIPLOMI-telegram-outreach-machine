from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID
from uuid import uuid4

import pytest

from backend.services.engagement_account_behavior import (
    ACCOUNT_HEALTH_REFRESH_HOURS,
    COLLECTION_NEXT_JITTER_MAX_MINUTES,
    COLLECTION_NEXT_JITTER_MIN_MINUTES,
    INITIAL_JOIN_READ_LIMIT,
    MAX_STARTED_OPPORTUNITIES_PER_ACCOUNT_4H,
    READ_RECEIPT_JITTER_MAX_MINUTES,
    READ_RECEIPT_JITTER_MIN_MINUTES,
    SEND_DELAY_MAX_SECONDS,
    SEND_DELAY_MIN_SECONDS,
    WARMUP_DURATION_MINUTES,
    engagement_send_delay_seconds,
    engagement_send_scheduled_at,
    engagement_wait_periods_disabled_for_community,
    post_join_warmup_skip_reason,
    stable_jitter_minutes,
    stable_jitter_seconds,
    utc_epoch_bucket,
)


def test_account_behavior_defaults_match_spec() -> None:
    assert SEND_DELAY_MIN_SECONDS == 45
    assert SEND_DELAY_MAX_SECONDS == 120
    assert INITIAL_JOIN_READ_LIMIT == 5
    assert WARMUP_DURATION_MINUTES == 60
    assert MAX_STARTED_OPPORTUNITIES_PER_ACCOUNT_4H == 3
    assert ACCOUNT_HEALTH_REFRESH_HOURS == 8


def test_stable_jitter_seconds_is_deterministic_and_in_range() -> None:
    candidate_id = uuid4()
    seed_parts = ("send-delay", candidate_id)

    first = stable_jitter_seconds(
        minimum_seconds=SEND_DELAY_MIN_SECONDS,
        maximum_seconds=SEND_DELAY_MAX_SECONDS,
        seed_parts=seed_parts,
    )
    second = stable_jitter_seconds(
        minimum_seconds=SEND_DELAY_MIN_SECONDS,
        maximum_seconds=SEND_DELAY_MAX_SECONDS,
        seed_parts=seed_parts,
    )

    assert first == second
    assert SEND_DELAY_MIN_SECONDS <= first <= SEND_DELAY_MAX_SECONDS


def test_engagement_send_scheduled_at_uses_stable_candidate_delay() -> None:
    candidate_id = uuid4()
    now = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    scheduled_at = engagement_send_scheduled_at(candidate_id, now=now)

    assert scheduled_at == now + timedelta(seconds=engagement_send_delay_seconds(candidate_id))
    assert SEND_DELAY_MIN_SECONDS <= (scheduled_at - now).total_seconds() <= SEND_DELAY_MAX_SECONDS


def test_engagement_send_scheduled_at_can_skip_wait_periods() -> None:
    candidate_id = uuid4()
    now = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    scheduled_at = engagement_send_scheduled_at(
        candidate_id,
        now=now,
        skip_wait_periods=True,
    )

    assert scheduled_at == now


def test_stable_jitter_minutes_supports_collection_and_read_ranges() -> None:
    community_id = uuid4()
    account_id = uuid4()

    collection_delay = stable_jitter_minutes(
        minimum_minutes=COLLECTION_NEXT_JITTER_MIN_MINUTES,
        maximum_minutes=COLLECTION_NEXT_JITTER_MAX_MINUTES,
        seed_parts=("collection-next", community_id),
    )
    read_delay = stable_jitter_minutes(
        minimum_minutes=READ_RECEIPT_JITTER_MIN_MINUTES,
        maximum_minutes=READ_RECEIPT_JITTER_MAX_MINUTES,
        seed_parts=("read-receipt", account_id, community_id),
    )

    assert COLLECTION_NEXT_JITTER_MIN_MINUTES <= collection_delay <= COLLECTION_NEXT_JITTER_MAX_MINUTES
    assert READ_RECEIPT_JITTER_MIN_MINUTES <= read_delay <= READ_RECEIPT_JITTER_MAX_MINUTES


def test_different_purposes_spread_jitter_values() -> None:
    identifier = uuid4()

    values = {
        stable_jitter_seconds(
            minimum_seconds=45,
            maximum_seconds=120,
            seed_parts=(purpose, identifier),
        )
        for purpose in ("send-delay", "collection-initial", "read-receipt", "health-refresh")
    }

    assert len(values) > 1


def test_utc_epoch_bucket_is_timezone_stable() -> None:
    value = datetime(2026, 4, 30, 12, 7, 30, tzinfo=timezone.utc)

    assert utc_epoch_bucket(value, bucket_seconds=300) == utc_epoch_bucket(
        value.replace(tzinfo=None),
        bucket_seconds=300,
    )


def test_post_join_warmup_skip_reason_can_skip_wait_periods() -> None:
    now = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
    joined_at = now - timedelta(minutes=30)

    skip_reason = post_join_warmup_skip_reason(
        joined_at=joined_at,
        now=now,
        skip_wait_periods=True,
    )

    assert skip_reason is None


def test_wait_period_bypass_matches_uuid_username_and_tg_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.services.engagement_account_behavior.get_settings",
        lambda: SimpleNamespace(
            engagement_wait_period_bypass_communities=(
                "@ExampleTest, 12345, https://t.me/AnotherTest, "
                "550e8400-e29b-41d4-a716-446655440000"
            )
        ),
    )

    assert engagement_wait_periods_disabled_for_community(username="@exampletest") is True
    assert engagement_wait_periods_disabled_for_community(username="anothertest") is True
    assert engagement_wait_periods_disabled_for_community(tg_id=12345) is True
    assert (
        engagement_wait_periods_disabled_for_community(
            community_id=UUID("550e8400-e29b-41d4-a716-446655440000")
        )
        is True
    )
    assert engagement_wait_periods_disabled_for_community(username="@not-listed") is False


@pytest.mark.parametrize(
    ("minimum", "maximum", "expected_message"),
    [
        (-1, 10, "minimum must be non-negative"),
        (10, 9, "maximum must be greater than or equal to minimum"),
    ],
)
def test_stable_jitter_rejects_invalid_ranges(
    minimum: int,
    maximum: int,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        stable_jitter_seconds(
            minimum_seconds=minimum,
            maximum_seconds=maximum,
            seed_parts=("invalid",),
        )


def test_stable_jitter_rejects_empty_seed_parts() -> None:
    with pytest.raises(ValueError, match="seed_parts must not be empty"):
        stable_jitter_minutes(
            minimum_minutes=1,
            maximum_minutes=15,
            seed_parts=(),
        )


def test_utc_epoch_bucket_rejects_non_positive_bucket() -> None:
    with pytest.raises(ValueError, match="bucket_seconds must be positive"):
        utc_epoch_bucket(datetime.now(timezone.utc), bucket_seconds=0)
