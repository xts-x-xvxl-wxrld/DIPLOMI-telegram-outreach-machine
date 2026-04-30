from __future__ import annotations

import uuid
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import EngagementActionStatus, EngagementOpportunityKind
from backend.db.models import EngagementAction, EngagementCandidate


@dataclass(frozen=True)
class OpportunityClassification:
    kind: str
    root_candidate_id: UUID | None = None


async def classify_candidate_opportunity(
    db: AsyncSession,
    *,
    community_id: UUID,
    selected_telegram_account_id: UUID | None,
    source_reply_to_tg_message_id: int | None,
) -> OpportunityClassification:
    if selected_telegram_account_id is None or source_reply_to_tg_message_id is None:
        return OpportunityClassification(kind=EngagementOpportunityKind.ROOT.value)

    previous_candidate = await db.scalar(
        select(EngagementCandidate)
        .join(EngagementAction, EngagementAction.candidate_id == EngagementCandidate.id)
        .where(
            EngagementAction.community_id == community_id,
            EngagementAction.telegram_account_id == selected_telegram_account_id,
            EngagementAction.status == EngagementActionStatus.SENT.value,
            EngagementAction.sent_tg_message_id == source_reply_to_tg_message_id,
        )
        .order_by(EngagementAction.sent_at.desc().nullslast(), EngagementAction.created_at.desc())
        .limit(1)
    )
    if previous_candidate is None:
        return OpportunityClassification(kind=EngagementOpportunityKind.ROOT.value)
    return OpportunityClassification(
        kind=EngagementOpportunityKind.CONTINUATION.value,
        root_candidate_id=previous_candidate.root_candidate_id or previous_candidate.id,
    )


def conversation_key(
    *,
    community_id: UUID,
    root_candidate_id: UUID | None,
    source_tg_message_id: int | None,
    source_excerpt: str | None,
) -> str:
    if root_candidate_id is not None:
        return f"community:{community_id}:root:{root_candidate_id}"
    if source_tg_message_id is not None:
        return f"community:{community_id}:source:{source_tg_message_id}"
    excerpt_hash = uuid.uuid5(uuid.NAMESPACE_URL, source_excerpt or "unknown")
    return f"community:{community_id}:source:{excerpt_hash}"


__all__ = ["OpportunityClassification", "classify_candidate_opportunity", "conversation_key"]
