from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import SearchAdapter, SearchRunStatus
from backend.db.models import SearchQuery, SearchRun
from backend.db.session import AsyncSessionLocal
from backend.queue.client import QueuedJob, enqueue_search_retrieve
from backend.queue.payloads import SearchPlanPayload
from backend.services.search import normalize_search_query_text


PLANNER_SOURCE = "deterministic_v1"
MAX_GENERATED_QUERIES = 5
SUPPORTED_PLANNER_ADAPTERS = {SearchAdapter.TELEGRAM_ENTITY_SEARCH.value}
TOKEN_PATTERN = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", flags=re.UNICODE)
EXCLUSION_PATTERN = re.compile(r"(?<!\S)-([^\W_]+(?:[-'][^\W_]+)*)", flags=re.UNICODE)


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


SearchRetrieveEnqueuer = Callable[..., QueuedJob]


class SearchPlanError(RuntimeError):
    pass


class SearchPlanValidationError(SearchPlanError):
    pass


@dataclass(frozen=True)
class PlannedSearchQuery:
    adapter: str
    query_text: str
    normalized_query_key: str
    include_terms: list[str]
    exclusion_terms: list[str]
    language_hint: str | None
    locale_hint: str | None
    planner_metadata: dict[str, Any]


@dataclass(frozen=True)
class SearchPlanningState:
    search_run_id: UUID
    search_run_status: str
    query_ids: list[UUID]
    query_count: int
    queries_created: int
    queries_reused: int
    planner_metadata: dict[str, Any]
    ready_for_retrieval: bool
    last_error: str | None = None


async def process_search_plan(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    enqueue_search_retrieve_fn: SearchRetrieveEnqueuer = enqueue_search_retrieve,
) -> dict[str, Any]:
    validated_payload = SearchPlanPayload.model_validate(payload)
    planning_state = await _plan_search_run(
        validated_payload,
        session_factory=session_factory,
    )

    retrieval_jobs: list[QueuedJob] = []
    if planning_state.ready_for_retrieval:
        for query_id in planning_state.query_ids:
            retrieval_jobs.append(
                enqueue_search_retrieve_fn(
                    planning_state.search_run_id,
                    query_id,
                    requested_by=validated_payload.requested_by,
                )
            )
        await _mark_run_retrieving(
            validated_payload.search_run_id,
            session_factory=session_factory,
            retrieval_jobs=retrieval_jobs,
        )
        planning_state = SearchPlanningState(
            search_run_id=planning_state.search_run_id,
            search_run_status=SearchRunStatus.RETRIEVING.value,
            query_ids=planning_state.query_ids,
            query_count=planning_state.query_count,
            queries_created=planning_state.queries_created,
            queries_reused=planning_state.queries_reused,
            planner_metadata=planning_state.planner_metadata,
            ready_for_retrieval=False,
            last_error=planning_state.last_error,
        )

    return {
        "status": "failed" if planning_state.last_error else "planned",
        "job_type": "search.plan",
        "search_run_id": str(planning_state.search_run_id),
        "search_run_status": planning_state.search_run_status,
        "planner_source": PLANNER_SOURCE,
        "query_ids": [str(query_id) for query_id in planning_state.query_ids],
        "query_count": planning_state.query_count,
        "queries_created": planning_state.queries_created,
        "queries_reused": planning_state.queries_reused,
        "retrieval_jobs": [_serialize_job(job) for job in retrieval_jobs],
        "last_error": planning_state.last_error,
    }


def build_deterministic_query_plans(
    raw_query: str,
    *,
    language_hints: list[str] | None = None,
    locale_hints: list[str] | None = None,
    enabled_adapters: list[str] | None = None,
) -> list[PlannedSearchQuery]:
    normalized_query = normalize_search_query_text(raw_query)
    exclusion_terms = _extract_exclusion_terms(normalized_query)
    include_terms = _tokenize_query_terms(EXCLUSION_PATTERN.sub(" ", normalized_query))
    if not include_terms:
        raise SearchPlanValidationError("Search query must include at least one search term")

    adapters = [adapter for adapter in (enabled_adapters or []) if adapter in SUPPORTED_PLANNER_ADAPTERS]
    if not adapters:
        adapters = [SearchAdapter.TELEGRAM_ENTITY_SEARCH.value]

    normalized_language_hints = _normalize_hint_list(language_hints or [], lowercase=True)
    normalized_locale_hints = _normalize_hint_list(locale_hints or [], lowercase=False)
    primary_language_hint = normalized_language_hints[0] if normalized_language_hints else None
    primary_locale_hint = normalized_locale_hints[0] if normalized_locale_hints else None
    generated_queries = _generate_query_variants(include_terms)

    plans: list[PlannedSearchQuery] = []
    for adapter in adapters:
        for index, query_terms in enumerate(generated_queries):
            query_text = " ".join(query_terms)
            plans.append(
                PlannedSearchQuery(
                    adapter=adapter,
                    query_text=query_text,
                    normalized_query_key=query_text,
                    include_terms=list(query_terms),
                    exclusion_terms=list(exclusion_terms),
                    language_hint=primary_language_hint,
                    locale_hint=primary_locale_hint,
                    planner_metadata={
                        "planner_source": PLANNER_SOURCE,
                        "variant_index": index,
                        "window_size": len(query_terms),
                        "language_hints": list(normalized_language_hints),
                        "locale_hints": list(normalized_locale_hints),
                    },
                )
            )
    return plans


def run_search_plan_job(payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(process_search_plan(payload))


async def _plan_search_run(
    payload: SearchPlanPayload,
    *,
    session_factory: Callable[[], AsyncSessionContext],
) -> SearchPlanningState:
    async with session_factory() as session:
        search_run = await session.get(SearchRun, payload.search_run_id)
        if search_run is None:
            raise SearchPlanError(f"Search run not found: {payload.search_run_id}")

        existing_queries = await _list_search_queries(session, search_run.id)
        if search_run.status in {
            SearchRunStatus.RETRIEVING.value,
            SearchRunStatus.RANKING.value,
            SearchRunStatus.COMPLETED.value,
            SearchRunStatus.CANCELLED.value,
        }:
            return SearchPlanningState(
                search_run_id=search_run.id,
                search_run_status=search_run.status,
                query_ids=[query.id for query in existing_queries],
                query_count=len(existing_queries),
                queries_created=0,
                queries_reused=len(existing_queries),
                planner_metadata=dict(search_run.planner_metadata or {}),
                ready_for_retrieval=False,
                last_error=search_run.last_error,
            )

        planning_started_at = datetime.now(timezone.utc)
        search_run.status = SearchRunStatus.PLANNING.value
        search_run.started_at = search_run.started_at or planning_started_at
        search_run.completed_at = None
        search_run.last_error = None
        search_run.planner_source = PLANNER_SOURCE
        search_run.updated_at = planning_started_at

        try:
            planned_queries = build_deterministic_query_plans(
                search_run.raw_query,
                language_hints=list(search_run.language_hints or []),
                locale_hints=list(search_run.locale_hints or []),
                enabled_adapters=list(search_run.enabled_adapters or []),
            )
        except SearchPlanValidationError as exc:
            search_run.status = SearchRunStatus.FAILED.value
            search_run.last_error = _truncate_error(str(exc))
            search_run.completed_at = planning_started_at
            search_run.updated_at = planning_started_at
            search_run.planner_metadata = {
                "planner_source": PLANNER_SOURCE,
                "failed_at": planning_started_at.isoformat(),
            }
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            return SearchPlanningState(
                search_run_id=search_run.id,
                search_run_status=search_run.status,
                query_ids=[],
                query_count=0,
                queries_created=0,
                queries_reused=0,
                planner_metadata=dict(search_run.planner_metadata or {}),
                ready_for_retrieval=False,
                last_error=search_run.last_error,
            )

        existing_by_key = {
            (query.adapter, query.normalized_query_key): query
            for query in existing_queries
        }
        now = datetime.now(timezone.utc)
        planned_query_models: list[SearchQuery] = []
        queries_created = 0
        queries_reused = 0

        for planned_query in planned_queries:
            existing_query = existing_by_key.get(
                (planned_query.adapter, planned_query.normalized_query_key)
            )
            if existing_query is not None:
                queries_reused += 1
                planned_query_models.append(existing_query)
                continue

            query_model = SearchQuery(
                id=uuid4(),
                search_run_id=search_run.id,
                adapter=planned_query.adapter,
                query_text=planned_query.query_text,
                normalized_query_key=planned_query.normalized_query_key,
                language_hint=planned_query.language_hint,
                locale_hint=planned_query.locale_hint,
                include_terms=list(planned_query.include_terms),
                exclusion_terms=list(planned_query.exclusion_terms),
                planner_source=PLANNER_SOURCE,
                planner_metadata=dict(planned_query.planner_metadata),
                created_at=now,
            )
            session.add(query_model)
            planned_query_models.append(query_model)
            queries_created += 1

        planner_metadata = _build_run_planner_metadata(
            search_run=search_run,
            payload=payload,
            planned_queries=planned_queries,
            queries_created=queries_created,
            queries_reused=queries_reused,
        )
        search_run.planner_metadata = planner_metadata
        search_run.updated_at = now

        try:
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        return SearchPlanningState(
            search_run_id=search_run.id,
            search_run_status=search_run.status,
            query_ids=[query.id for query in planned_query_models],
            query_count=len(planned_query_models),
            queries_created=queries_created,
            queries_reused=queries_reused,
            planner_metadata=planner_metadata,
            ready_for_retrieval=bool(planned_query_models),
            last_error=None,
        )


async def _mark_run_retrieving(
    search_run_id: UUID,
    *,
    session_factory: Callable[[], AsyncSessionContext],
    retrieval_jobs: list[QueuedJob],
) -> None:
    async with session_factory() as session:
        search_run = await session.get(SearchRun, search_run_id)
        if search_run is None:
            raise SearchPlanError(f"Search run not found: {search_run_id}")

        updated_at = datetime.now(timezone.utc)
        planner_metadata = dict(search_run.planner_metadata or {})
        planner_metadata["retrieval_jobs"] = [job.id for job in retrieval_jobs]
        planner_metadata["retrieval_enqueued_at"] = updated_at.isoformat()

        search_run.status = SearchRunStatus.RETRIEVING.value
        search_run.planner_metadata = planner_metadata
        search_run.updated_at = updated_at

        try:
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _list_search_queries(session: AsyncSession, search_run_id: UUID) -> list[SearchQuery]:
    return list(
        (
            await session.scalars(
                select(SearchQuery)
                .where(SearchQuery.search_run_id == search_run_id)
                .order_by(SearchQuery.created_at.asc(), SearchQuery.id.asc())
            )
        ).all()
    )


def _build_run_planner_metadata(
    *,
    search_run: SearchRun,
    payload: SearchPlanPayload,
    planned_queries: list[PlannedSearchQuery],
    queries_created: int,
    queries_reused: int,
) -> dict[str, Any]:
    normalized_query = normalize_search_query_text(search_run.raw_query)
    include_terms = _tokenize_query_terms(EXCLUSION_PATTERN.sub(" ", normalized_query))
    exclusion_terms = _extract_exclusion_terms(normalized_query)
    language_hints = _normalize_hint_list(list(search_run.language_hints or []), lowercase=True)
    locale_hints = _normalize_hint_list(list(search_run.locale_hints or []), lowercase=False)
    return {
        "planner_source": PLANNER_SOURCE,
        "requested_by": payload.requested_by or search_run.requested_by,
        "normalized_query": normalized_query.casefold(),
        "include_terms": include_terms,
        "exclusion_terms": exclusion_terms,
        "language_hints": language_hints,
        "locale_hints": locale_hints,
        "generated_query_count": len(planned_queries),
        "queries_created": queries_created,
        "queries_reused": queries_reused,
        "adapters": sorted({query.adapter for query in planned_queries}),
    }


def _generate_query_variants(include_terms: list[str]) -> list[list[str]]:
    variants: list[list[str]] = []
    seen: set[str] = set()

    def add_variant(terms: list[str]) -> None:
        if not terms or len(variants) >= MAX_GENERATED_QUERIES:
            return
        key = " ".join(terms)
        if key in seen:
            return
        seen.add(key)
        variants.append(list(terms))

    add_variant(include_terms)

    max_window_size = min(3, len(include_terms) - 1)
    for window_size in range(max_window_size, 1, -1):
        for start in range(0, len(include_terms) - window_size + 1):
            add_variant(include_terms[start : start + window_size])
            if len(variants) >= MAX_GENERATED_QUERIES:
                return variants

    return variants


def _tokenize_query_terms(raw_query: str) -> list[str]:
    normalized_terms: list[str] = []
    seen: set[str] = set()
    for match in TOKEN_PATTERN.findall(raw_query):
        term = match.casefold()
        if not term or term in seen:
            continue
        seen.add(term)
        normalized_terms.append(term)
    return normalized_terms


def _extract_exclusion_terms(raw_query: str) -> list[str]:
    exclusion_terms: list[str] = []
    seen: set[str] = set()
    for match in EXCLUSION_PATTERN.findall(raw_query):
        term = match.casefold()
        if not term or term in seen:
            continue
        seen.add(term)
        exclusion_terms.append(term)
    return exclusion_terms


def _normalize_hint_list(values: list[str], *, lowercase: bool) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = " ".join(value.split()).strip()
        if not item:
            continue
        item = item.casefold() if lowercase else item.upper()
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _serialize_job(job: QueuedJob) -> dict[str, str]:
    return {"id": job.id, "type": job.type, "status": job.status}


def _truncate_error(message: str, limit: int = 200) -> str:
    if len(message) <= limit:
        return message
    return f"{message[: limit - 3].rstrip()}..."


__all__ = [
    "PLANNER_SOURCE",
    "MAX_GENERATED_QUERIES",
    "SearchPlanError",
    "SearchPlanValidationError",
    "PlannedSearchQuery",
    "SearchPlanningState",
    "build_deterministic_query_plans",
    "process_search_plan",
    "run_search_plan_job",
]
