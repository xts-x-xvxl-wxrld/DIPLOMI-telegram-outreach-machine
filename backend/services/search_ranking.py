from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.enums import (
    SearchCandidateStatus,
    SearchEvidenceType,
    SearchReviewAction,
    SearchRunStatus,
)
from backend.db.models import SearchCandidate, SearchCandidateEvidence, SearchReview, SearchRun

RANKING_VERSION = "search_rank_v1"
COMPONENT_WEIGHTS = {
    "title_username_match": Decimal("40"),
    "description_match": Decimal("25"),
    "cross_query_confirmation": Decimal("15"),
    "cross_adapter_confirmation": Decimal("10"),
    "activity_hint": Decimal("10"),
    "prior_run_rejection_penalty": Decimal("-25"),
    "spam_penalty": Decimal("-30"),
}
STATUS_ORDER = {
    SearchCandidateStatus.PROMOTED.value: 0,
    SearchCandidateStatus.CANDIDATE.value: 1,
    SearchCandidateStatus.ARCHIVED.value: 2,
    SearchCandidateStatus.REJECTED.value: 3,
    SearchCandidateStatus.CONVERTED_TO_SEED.value: 4,
}
SPAM_TEXT_PATTERN = re.compile(
    r"\b(airdrop|betting|casino|giveaway|guaranteed\s+profit|pump|spam)\b",
    flags=re.IGNORECASE,
)
REPEATED_PUNCTUATION_PATTERN = re.compile(r"([!?$])\1{3,}")


class SearchRankingError(RuntimeError):
    pass


class SearchRankingNotFound(SearchRankingError):
    pass


class SearchRankingValidationError(SearchRankingError):
    pass


@dataclass(frozen=True)
class CandidateRankResult:
    candidate_id: UUID
    score: Decimal
    score_components: dict[str, int | float]


@dataclass(frozen=True)
class SearchRankingSummary:
    search_run_id: UUID
    run_status: str
    ranking_version: str
    ranked_candidate_ids: list[UUID]
    candidate_count: int
    requested_by: str | None
    ranked_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "ranked",
            "job_type": "search.rank",
            "search_run_id": str(self.search_run_id),
            "search_run_status": self.run_status,
            "ranking_version": self.ranking_version,
            "ranked_candidate_ids": [str(candidate_id) for candidate_id in self.ranked_candidate_ids],
            "candidate_count": self.candidate_count,
            "requested_by": self.requested_by,
            "ranked_at": self.ranked_at.isoformat(),
        }


class SearchRankingRepository(Protocol):
    async def get_search_run(self, search_run_id: UUID) -> SearchRun | None:
        pass

    async def list_candidates(self, search_run_id: UUID) -> list[SearchCandidate]:
        pass

    async def list_evidence(self, search_run_id: UUID) -> list[SearchCandidateEvidence]:
        pass

    async def list_prior_rejected_community_ids(
        self,
        *,
        search_run: SearchRun,
        community_ids: set[UUID],
    ) -> set[UUID]:
        pass

    async def flush(self) -> None:
        pass


class SqlAlchemySearchRankingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_search_run(self, search_run_id: UUID) -> SearchRun | None:
        return await self.session.get(SearchRun, search_run_id)

    async def list_candidates(self, search_run_id: UUID) -> list[SearchCandidate]:
        return list(
            (
                await self.session.scalars(
                    select(SearchCandidate)
                    .where(SearchCandidate.search_run_id == search_run_id)
                    .options(joinedload(SearchCandidate.community))
                    .order_by(SearchCandidate.first_seen_at.asc(), SearchCandidate.id.asc())
                )
            ).all()
        )

    async def list_evidence(self, search_run_id: UUID) -> list[SearchCandidateEvidence]:
        return list(
            (
                await self.session.scalars(
                    select(SearchCandidateEvidence)
                    .where(SearchCandidateEvidence.search_run_id == search_run_id)
                    .order_by(SearchCandidateEvidence.captured_at.asc(), SearchCandidateEvidence.id.asc())
                )
            ).all()
        )

    async def list_prior_rejected_community_ids(
        self,
        *,
        search_run: SearchRun,
        community_ids: set[UUID],
    ) -> set[UUID]:
        if not community_ids:
            return set()
        rows = await self.session.scalars(
            select(SearchReview.community_id)
            .where(SearchReview.community_id.in_(community_ids))
            .where(
                or_(
                    and_(
                        SearchReview.action == SearchReviewAction.REJECT.value,
                        SearchReview.search_run_id != search_run.id,
                        SearchReview.created_at < search_run.created_at,
                    ),
                    SearchReview.action == SearchReviewAction.GLOBAL_REJECT.value,
                )
            )
        )
        return {community_id for community_id in rows.all() if community_id is not None}

    async def flush(self) -> None:
        await self.session.flush()


async def rank_search_candidates(
    repository: SearchRankingRepository,
    *,
    search_run_id: UUID,
    requested_by: str | None = None,
) -> SearchRankingSummary:
    search_run = await repository.get_search_run(search_run_id)
    if search_run is None:
        raise SearchRankingNotFound(f"Search run not found: {search_run_id}")
    if search_run.status == SearchRunStatus.CANCELLED.value:
        raise SearchRankingValidationError("Search run is cancelled")

    now = datetime.now(timezone.utc)
    search_run.status = SearchRunStatus.RANKING.value
    search_run.completed_at = None
    search_run.last_error = None
    search_run.updated_at = now

    candidates = await repository.list_candidates(search_run.id)
    evidence_rows = await repository.list_evidence(search_run.id)
    evidence_by_candidate = _group_evidence(evidence_rows)
    prior_rejected_community_ids = await repository.list_prior_rejected_community_ids(
        search_run=search_run,
        community_ids={
            candidate.community_id
            for candidate in candidates
            if candidate.community_id is not None
        },
    )

    results: list[CandidateRankResult] = []
    for candidate in candidates:
        result = score_candidate(
            candidate,
            evidence_by_candidate.get(candidate.id, []),
            prior_rejected_community_ids=prior_rejected_community_ids,
        )
        candidate.score = result.score
        candidate.score_components = dict(result.score_components)
        candidate.ranking_version = RANKING_VERSION
        results.append(result)

    ranked_candidates = sorted(
        candidates,
        key=lambda candidate: _candidate_sort_key(
            candidate,
            evidence_count=len(evidence_by_candidate.get(candidate.id, [])),
        ),
    )
    ranked_at = datetime.now(timezone.utc)
    search_run.status = SearchRunStatus.COMPLETED.value
    search_run.ranking_version = RANKING_VERSION
    search_run.ranking_metadata = {
        **dict(search_run.ranking_metadata or {}),
        "ranking_version": RANKING_VERSION,
        "ranked_at": ranked_at.isoformat(),
        "requested_by": requested_by or search_run.requested_by,
        "candidate_count": len(candidates),
        "component_weights": _serialized_weights(),
        "ranked_candidate_ids": [str(candidate.id) for candidate in ranked_candidates],
    }
    search_run.completed_at = ranked_at
    search_run.updated_at = ranked_at

    await repository.flush()
    return SearchRankingSummary(
        search_run_id=search_run.id,
        run_status=search_run.status,
        ranking_version=RANKING_VERSION,
        ranked_candidate_ids=[candidate.id for candidate in ranked_candidates],
        candidate_count=len(results),
        requested_by=requested_by or search_run.requested_by,
        ranked_at=ranked_at,
    )


def score_candidate(
    candidate: SearchCandidate,
    evidence_rows: list[SearchCandidateEvidence],
    *,
    prior_rejected_community_ids: set[UUID],
) -> CandidateRankResult:
    evidence_types = {row.evidence_type for row in evidence_rows}
    distinct_query_ids = {row.search_query_id for row in evidence_rows if row.search_query_id is not None}
    distinct_query_texts = {
        _normalized_text(row.query_text)
        for row in evidence_rows
        if row.query_text is not None and _normalized_text(row.query_text)
    }
    distinct_adapters = {row.adapter for row in evidence_rows if row.adapter}

    components: dict[str, Decimal] = {
        "title_username_match": (
            COMPONENT_WEIGHTS["title_username_match"]
            if evidence_types
            & {
                SearchEvidenceType.ENTITY_TITLE_MATCH.value,
                SearchEvidenceType.ENTITY_USERNAME_MATCH.value,
            }
            else Decimal("0")
        ),
        "description_match": (
            COMPONENT_WEIGHTS["description_match"]
            if SearchEvidenceType.DESCRIPTION_MATCH.value in evidence_types
            else Decimal("0")
        ),
        "cross_query_confirmation": (
            COMPONENT_WEIGHTS["cross_query_confirmation"]
            if len(distinct_query_ids) >= 2 or len(distinct_query_texts) >= 2
            else Decimal("0")
        ),
        "cross_adapter_confirmation": (
            COMPONENT_WEIGHTS["cross_adapter_confirmation"]
            if len(distinct_adapters) >= 2
            else Decimal("0")
        ),
        "activity_hint": _activity_hint(_candidate_member_count(candidate)),
        "prior_run_rejection_penalty": (
            COMPONENT_WEIGHTS["prior_run_rejection_penalty"]
            if candidate.community_id in prior_rejected_community_ids
            else Decimal("0")
        ),
        "spam_penalty": (
            COMPONENT_WEIGHTS["spam_penalty"]
            if _looks_spammy(candidate, evidence_rows)
            else Decimal("0")
        ),
    }
    score = sum(components.values(), Decimal("0")).quantize(Decimal("0.001"))
    return CandidateRankResult(
        candidate_id=candidate.id,
        score=score,
        score_components={
            name: _json_number(value)
            for name, value in components.items()
        },
    )


def _group_evidence(
    evidence_rows: list[SearchCandidateEvidence],
) -> dict[UUID, list[SearchCandidateEvidence]]:
    grouped: dict[UUID, list[SearchCandidateEvidence]] = {}
    for row in evidence_rows:
        grouped.setdefault(row.search_candidate_id, []).append(row)
    return grouped


def _activity_hint(member_count: int | None) -> Decimal:
    if member_count is None or member_count <= 0:
        return Decimal("0")
    if member_count >= 1000:
        return Decimal("10")
    if member_count >= 250:
        return Decimal("7.5")
    if member_count >= 50:
        return Decimal("5")
    return Decimal("2.5")


def _candidate_member_count(candidate: SearchCandidate) -> int | None:
    community = getattr(candidate, "community", None)
    if community is not None and community.member_count is not None:
        return community.member_count
    return candidate.raw_member_count


def _looks_spammy(
    candidate: SearchCandidate,
    evidence_rows: list[SearchCandidateEvidence],
) -> bool:
    text = " ".join(
        value
        for value in [
            candidate.raw_title,
            candidate.normalized_username,
            candidate.raw_description,
            *(row.evidence_value for row in evidence_rows),
        ]
        if value
    )
    if not text:
        return False
    return bool(SPAM_TEXT_PATTERN.search(text) or REPEATED_PUNCTUATION_PATTERN.search(text))


def _candidate_sort_key(candidate: SearchCandidate, *, evidence_count: int) -> tuple[object, ...]:
    title = _candidate_title(candidate)
    return (
        -float(candidate.score or 0),
        STATUS_ORDER.get(candidate.status, 5),
        -evidence_count,
        title is None,
        (title or "").casefold(),
        candidate.first_seen_at,
        str(candidate.id),
    )


def _candidate_title(candidate: SearchCandidate) -> str | None:
    community = getattr(candidate, "community", None)
    if community is not None and community.title:
        return community.title
    return candidate.raw_title


def _normalized_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split()).casefold()


def _serialized_weights() -> dict[str, int | float]:
    return {
        name: _json_number(value)
        for name, value in COMPONENT_WEIGHTS.items()
    }


def _json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


__all__ = [
    "COMPONENT_WEIGHTS",
    "RANKING_VERSION",
    "CandidateRankResult",
    "SearchRankingError",
    "SearchRankingNotFound",
    "SearchRankingRepository",
    "SearchRankingSummary",
    "SearchRankingValidationError",
    "SqlAlchemySearchRankingRepository",
    "rank_search_candidates",
    "score_candidate",
]
