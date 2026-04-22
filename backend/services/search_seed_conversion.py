from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import (
    SearchCandidateStatus,
    SearchEvidenceType,
    SearchReviewAction,
    SearchReviewScope,
    SeedChannelStatus,
)
from backend.db.models import (
    Community,
    SearchCandidate,
    SearchCandidateEvidence,
    SearchReview,
    SearchRun,
    SeedChannel,
    SeedGroup,
)
from backend.services.search import SearchNotFound, SearchValidationError
from backend.services.seed_import import NormalizedSeed, normalize_telegram_seed


@dataclass(frozen=True)
class SearchSeedConversionResult:
    seed_group: SeedGroup
    seed_channel: SeedChannel
    candidate: SearchCandidate
    review: SearchReview


async def convert_search_candidate_to_seed(
    db: AsyncSession,
    *,
    candidate_id: UUID,
    seed_group_name: str | None = None,
    requested_by: str | None = None,
) -> SearchSeedConversionResult:
    candidate = await db.get(SearchCandidate, candidate_id)
    if candidate is None:
        raise SearchNotFound("not_found", "Search candidate not found")

    search_run = await db.get(SearchRun, candidate.search_run_id)
    community = await _candidate_community(db, candidate)
    normalized_seed = _candidate_seed(candidate, community)
    group_name = _conversion_group_name(seed_group_name, search_run)
    seed_group = await _get_or_create_seed_group(db, group_name, requested_by=requested_by)
    seed_channel = await _get_or_create_seed_channel(
        db,
        seed_group=seed_group,
        normalized_seed=normalized_seed,
        candidate=candidate,
        community=community,
    )

    reviewed_at = datetime.now(timezone.utc)
    candidate.status = SearchCandidateStatus.CONVERTED_TO_SEED.value
    candidate.reviewed_at = reviewed_at
    candidate.last_reviewed_by = requested_by or "operator"

    review = SearchReview(
        id=uuid4(),
        search_run_id=candidate.search_run_id,
        search_candidate_id=candidate.id,
        community_id=candidate.community_id,
        action=SearchReviewAction.CONVERT_TO_SEED.value,
        scope=SearchReviewScope.RUN.value,
        requested_by=requested_by,
        review_metadata={
            "seed_group_id": str(seed_group.id),
            "seed_channel_id": str(seed_channel.id),
        },
        created_at=reviewed_at,
    )
    evidence = SearchCandidateEvidence(
        id=uuid4(),
        search_run_id=candidate.search_run_id,
        search_candidate_id=candidate.id,
        community_id=candidate.community_id,
        adapter="operator_review",
        evidence_type=SearchEvidenceType.MANUAL_SEED.value,
        evidence_value=f"Converted to seed group: {seed_group.name}"[:500],
        evidence_metadata={
            "seed_group_id": str(seed_group.id),
            "seed_channel_id": str(seed_channel.id),
            "search_candidate_id": str(candidate.id),
        },
        source_seed_group_id=seed_group.id,
        source_seed_channel_id=seed_channel.id,
        captured_at=reviewed_at,
    )
    db.add(review)
    db.add(evidence)
    await db.flush()
    return SearchSeedConversionResult(
        seed_group=seed_group,
        seed_channel=seed_channel,
        candidate=candidate,
        review=review,
    )


async def _candidate_community(db: AsyncSession, candidate: SearchCandidate) -> Community | None:
    loaded = candidate.__dict__.get("community")
    if loaded is not None:
        return loaded
    if candidate.community_id is None:
        return None
    return await db.get(Community, candidate.community_id)


def _candidate_seed(candidate: SearchCandidate, community: Community | None) -> NormalizedSeed:
    seed_ref = (
        candidate.canonical_url
        or _url_from_username(candidate.normalized_username)
        or (community.telegram_url if community is not None else None)
        or _url_from_username(community.username if community is not None else None)
    )
    if seed_ref is None:
        raise SearchValidationError(
            "missing_public_reference",
            "Search candidate needs a public username or canonical URL before seed conversion",
        )
    try:
        return normalize_telegram_seed(seed_ref)
    except ValueError as exc:
        raise SearchValidationError("invalid_public_reference", str(exc)) from exc


def _url_from_username(username: str | None) -> str | None:
    if not username:
        return None
    return f"https://t.me/{username.lstrip('@')}"


def _conversion_group_name(seed_group_name: str | None, search_run: SearchRun | None) -> str:
    if seed_group_name and seed_group_name.strip():
        return " ".join(seed_group_name.split())
    if search_run is not None and search_run.normalized_title:
        return f"Search: {search_run.normalized_title}"
    return "Search conversions"


async def _get_or_create_seed_group(
    db: AsyncSession,
    name: str,
    *,
    requested_by: str | None,
) -> SeedGroup:
    normalized_name = " ".join(name.strip().split()).casefold()
    seed_group = await db.scalar(
        select(SeedGroup).where(SeedGroup.normalized_name == normalized_name)
    )
    if seed_group is not None:
        return seed_group

    seed_group = SeedGroup(
        id=uuid4(),
        name=name,
        normalized_name=normalized_name,
        created_by=requested_by,
    )
    db.add(seed_group)
    await db.flush()
    return seed_group


async def _get_or_create_seed_channel(
    db: AsyncSession,
    *,
    seed_group: SeedGroup,
    normalized_seed: NormalizedSeed,
    candidate: SearchCandidate,
    community: Community | None,
) -> SeedChannel:
    seed_channel = await db.scalar(
        select(SeedChannel).where(
            SeedChannel.seed_group_id == seed_group.id,
            SeedChannel.normalized_key == normalized_seed.normalized_key,
        )
    )
    title = (community.title if community is not None else None) or candidate.raw_title
    if seed_channel is not None:
        if candidate.community_id is not None and seed_channel.community_id is None:
            seed_channel.community_id = candidate.community_id
        if title and not seed_channel.title:
            seed_channel.title = title
        seed_channel.raw_value = normalized_seed.telegram_url
        seed_channel.username = normalized_seed.username
        seed_channel.telegram_url = normalized_seed.telegram_url
        return seed_channel

    seed_channel = SeedChannel(
        id=uuid4(),
        seed_group_id=seed_group.id,
        raw_value=normalized_seed.telegram_url,
        normalized_key=normalized_seed.normalized_key,
        username=normalized_seed.username,
        telegram_url=normalized_seed.telegram_url,
        title=title,
        notes=f"Converted from search candidate {candidate.id}",
        status=(
            SeedChannelStatus.RESOLVED.value
            if candidate.community_id is not None
            else SeedChannelStatus.PENDING.value
        ),
        community_id=candidate.community_id,
    )
    db.add(seed_channel)
    await db.flush()
    return seed_channel


__all__ = ["SearchSeedConversionResult", "convert_search_candidate_to_seed"]
