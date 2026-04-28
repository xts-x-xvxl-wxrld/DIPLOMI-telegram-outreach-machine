from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import EngagementCandidateStatus
from backend.db.models import EngagementCandidate, EngagementDraftUpdateRequest


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_draft_update_request_by_source_candidate(
    db: AsyncSession,
    *,
    source_candidate_id: UUID,
) -> EngagementDraftUpdateRequest | None:
    return await db.scalar(
        select(EngagementDraftUpdateRequest)
        .where(EngagementDraftUpdateRequest.source_candidate_id == source_candidate_id)
        .limit(1)
    )


async def has_active_draft_update_request(
    db: AsyncSession,
    *,
    source_candidate_id: UUID,
) -> bool:
    request = await get_draft_update_request_by_source_candidate(
        db,
        source_candidate_id=source_candidate_id,
    )
    return request is not None and request.status == "pending"


async def complete_draft_update_request(
    db: AsyncSession,
    *,
    source_candidate_id: UUID,
    replacement_candidate_id: UUID,
    completed_at: datetime | None = None,
) -> EngagementDraftUpdateRequest | None:
    request = await get_draft_update_request_by_source_candidate(
        db,
        source_candidate_id=source_candidate_id,
    )
    if request is None:
        return None
    if request.status == "completed":
        if request.replacement_candidate_id == replacement_candidate_id:
            return request
        return None
    if request.status != "pending":
        return None

    source_candidate = await db.get(EngagementCandidate, source_candidate_id)
    replacement_candidate = await db.get(EngagementCandidate, replacement_candidate_id)
    if source_candidate is None or replacement_candidate is None:
        return None
    if replacement_candidate.id == source_candidate.id:
        return None
    if replacement_candidate.status != EngagementCandidateStatus.NEEDS_REVIEW.value:
        return None
    if (
        replacement_candidate.community_id != source_candidate.community_id
        or replacement_candidate.topic_id != source_candidate.topic_id
    ):
        return None

    finished_at = completed_at or _utcnow()
    request.replacement_candidate_id = replacement_candidate.id
    request.status = "completed"
    request.completed_at = finished_at
    request.updated_at = finished_at
    await db.flush()
    return request


__all__ = [
    "complete_draft_update_request",
    "get_draft_update_request_by_source_candidate",
    "has_active_draft_update_request",
]
