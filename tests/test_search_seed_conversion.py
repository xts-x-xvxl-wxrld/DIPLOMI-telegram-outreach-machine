from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.db.enums import SearchCandidateStatus, SearchReviewAction
from backend.db.models import Community, SearchCandidate, SearchCandidateEvidence, SearchReview, SearchRun, SeedChannel
from backend.services.search import SearchValidationError
from backend.services.search_seed_conversion import convert_search_candidate_to_seed


@pytest.mark.asyncio
async def test_convert_search_candidate_to_seed_reuses_existing_seed_channel() -> None:
    run_id = uuid4()
    community_id = uuid4()
    seed_group = _seed_group()
    existing_channel = SeedChannel(
        id=uuid4(),
        seed_group_id=seed_group.id,
        raw_value="https://t.me/husaas",
        normalized_key="username:husaas",
        username="husaas",
        telegram_url="https://t.me/husaas",
        status="resolved",
        community_id=community_id,
    )
    candidate = SearchCandidate(
        id=uuid4(),
        search_run_id=run_id,
        community_id=community_id,
        status=SearchCandidateStatus.PROMOTED.value,
        normalized_username="husaas",
        score_components={},
        first_seen_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    db = _FakeDb(
        search_run=SearchRun(
            id=run_id,
            raw_query="Hungarian SaaS",
            normalized_title="Hungarian SaaS",
            status="completed",
            enabled_adapters=["telegram_entity_search"],
            language_hints=[],
            locale_hints=[],
            per_run_candidate_cap=100,
            per_adapter_caps={},
            planner_metadata={},
            ranking_metadata={},
            created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        ),
        candidate=candidate,
        community=Community(id=community_id, tg_id=123, username="husaas"),
        scalars=[seed_group, existing_channel],
    )

    result = await convert_search_candidate_to_seed(
        db,  # type: ignore[arg-type]
        candidate_id=candidate.id,
        requested_by="telegram:123",
    )

    assert result.seed_channel.id == existing_channel.id
    assert candidate.status == SearchCandidateStatus.CONVERTED_TO_SEED.value
    assert not any(isinstance(item, SeedChannel) for item in db.added)
    assert any(isinstance(item, SearchReview) for item in db.added)
    assert any(isinstance(item, SearchCandidateEvidence) for item in db.added)
    review = next(item for item in db.added if isinstance(item, SearchReview))
    assert review.action == SearchReviewAction.CONVERT_TO_SEED.value
    assert review.review_metadata["seed_channel_id"] == str(existing_channel.id)


@pytest.mark.asyncio
async def test_convert_search_candidate_to_seed_requires_public_reference() -> None:
    candidate = SearchCandidate(
        id=uuid4(),
        search_run_id=uuid4(),
        status=SearchCandidateStatus.PROMOTED.value,
        score_components={},
        first_seen_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    db = _FakeDb(candidate=candidate, scalars=[])

    with pytest.raises(SearchValidationError) as exc_info:
        await convert_search_candidate_to_seed(db, candidate_id=candidate.id)  # type: ignore[arg-type]

    assert exc_info.value.code == "missing_public_reference"


def _seed_group():
    from backend.db.models import SeedGroup

    return SeedGroup(
        id=uuid4(),
        name="Search: Hungarian SaaS",
        normalized_name="search: hungarian saas",
        created_by="telegram:123",
    )


class _FakeDb:
    def __init__(
        self,
        *,
        search_run: SearchRun | None = None,
        candidate: SearchCandidate | None = None,
        community: Community | None = None,
        scalars: list[object | None] | None = None,
    ) -> None:
        self.search_run = search_run
        self.candidate = candidate
        self.community = community
        self.scalars = list(scalars or [])
        self.added: list[object] = []
        self.flushes = 0

    async def get(self, model: object, item_id: object) -> object | None:
        del item_id
        if model is SearchCandidate:
            return self.candidate
        if model is SearchRun:
            return self.search_run
        if model is Community:
            return self.community
        return None

    async def scalar(self, statement: object) -> object | None:
        del statement
        if not self.scalars:
            return None
        return self.scalars.pop(0)

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        self.flushes += 1
