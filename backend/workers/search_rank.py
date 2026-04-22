from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import SearchRankPayload
from backend.services.search_ranking import (
    SearchRankingSummary,
    SqlAlchemySearchRankingRepository,
    rank_search_candidates,
)


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


RankSearchCandidatesFn = Callable[..., Any]


async def process_search_rank(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    rank_search_candidates_fn: RankSearchCandidatesFn = rank_search_candidates,
) -> dict[str, object]:
    validated_payload = SearchRankPayload.model_validate(payload)
    async with session_factory() as session:
        try:
            summary: SearchRankingSummary = await rank_search_candidates_fn(
                SqlAlchemySearchRankingRepository(session),
                search_run_id=validated_payload.search_run_id,
                requested_by=validated_payload.requested_by,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return summary.to_dict()


def run_search_rank_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_search_rank(payload))


__all__ = ["process_search_rank", "run_search_rank_job"]
