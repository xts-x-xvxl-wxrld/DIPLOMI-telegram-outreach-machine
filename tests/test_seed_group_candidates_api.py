from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.api.routes.seeds import _build_seed_group_candidate_items
from backend.db.models import Community, CommunityDiscoveryEdge, SeedChannel


def test_build_seed_group_candidate_items_merges_manual_and_discovery_evidence() -> None:
    seed_group_id = uuid4()
    community_id = uuid4()
    seed_channel_id = uuid4()
    community = Community(
        id=community_id,
        tg_id=100,
        username="founder_circle",
        title="Founder Circle",
        status="candidate",
        store_messages=False,
        first_seen_at=datetime.now(timezone.utc),
    )
    seed_channel = SeedChannel(
        id=seed_channel_id,
        seed_group_id=seed_group_id,
        raw_value="@founder_circle",
        normalized_key="username:founder_circle",
        username="founder_circle",
        telegram_url="https://t.me/founder_circle",
        status="resolved",
        community_id=community_id,
    )
    mention_edge = CommunityDiscoveryEdge(
        id=uuid4(),
        seed_group_id=seed_group_id,
        seed_channel_id=seed_channel_id,
        source_community_id=community_id,
        target_community_id=community_id,
        evidence_type="mention",
        evidence_value="@founder_circle",
    )
    link_edge = CommunityDiscoveryEdge(
        id=uuid4(),
        seed_group_id=seed_group_id,
        seed_channel_id=seed_channel_id,
        source_community_id=community_id,
        target_community_id=community_id,
        evidence_type="telegram_link",
        evidence_value="https://t.me/founder_circle",
    )

    items = _build_seed_group_candidate_items(
        seed_group_id=seed_group_id,
        resolved_seed_rows=[(seed_channel, community)],
        discovered_rows=[(mention_edge, community), (link_edge, community)],
        status_value="candidate",
        include_rejected=False,
    )

    assert len(items) == 1
    item = items[0]
    assert item.community.id == community_id
    assert item.source_seed_count == 1
    assert item.evidence_count == 3
    assert item.evidence_types == ["manual_seed", "mention", "telegram_link"]
    assert item.candidate_score > 0


def test_build_seed_group_candidate_items_filters_out_rejected_by_default() -> None:
    seed_group_id = uuid4()
    community_id = uuid4()
    community = Community(
        id=community_id,
        tg_id=101,
        title="Rejected Community",
        status="rejected",
        store_messages=False,
        first_seen_at=datetime.now(timezone.utc),
    )
    seed_channel = SeedChannel(
        id=uuid4(),
        seed_group_id=seed_group_id,
        raw_value="@rejected",
        normalized_key="username:rejected",
        username="rejected",
        telegram_url="https://t.me/rejected",
        status="resolved",
        community_id=community_id,
    )

    items = _build_seed_group_candidate_items(
        seed_group_id=seed_group_id,
        resolved_seed_rows=[(seed_channel, community)],
        discovered_rows=[],
        status_value=None,
        include_rejected=False,
    )

    assert items == []
