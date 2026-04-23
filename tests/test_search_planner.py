from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.db.enums import SearchRunStatus
from backend.db.models import SearchQuery, SearchRun
from backend.queue.client import QueuedJob
from backend.workers.search_plan import build_deterministic_query_plans, process_search_plan


def test_build_deterministic_query_plans_generates_base_and_window_variants() -> None:
    plans = build_deterministic_query_plans(
        "Hungarian SaaS founders",
        language_hints=["hu", "en"],
        locale_hints=["HU"],
        enabled_adapters=["telegram_entity_search"],
    )

    assert [plan.query_text for plan in plans] == [
        "hungarian saas founders",
        "hungarian saas",
        "saas founders",
    ]
    assert plans[0].language_hint == "hu"
    assert plans[0].locale_hint == "HU"


def test_build_deterministic_query_plans_marks_deferred_adapters_skipped() -> None:
    plans = build_deterministic_query_plans(
        "Hungarian SaaS founders",
        enabled_adapters=["telegram_entity_search", "telegram_post_search", "web_search_tme"],
    )

    active_plans = [plan for plan in plans if plan.adapter == "telegram_entity_search"]
    deferred_plans = [plan for plan in plans if plan.adapter != "telegram_entity_search"]

    assert [plan.query_text for plan in active_plans] == [
        "hungarian saas founders",
        "hungarian saas",
        "saas founders",
    ]
    assert {plan.adapter for plan in deferred_plans} == {"telegram_post_search", "web_search_tme"}
    assert {plan.status for plan in deferred_plans} == {"skipped"}
    assert all(plan.planner_metadata["deferred"] is True for plan in deferred_plans)


def test_build_deterministic_query_plans_dedupes_duplicate_terms() -> None:
    plans = build_deterministic_query_plans(
        "  SaaS  saas founders FOUNDERS  ",
        enabled_adapters=["telegram_entity_search"],
    )

    assert [plan.query_text for plan in plans] == ["saas founders"]
    assert plans[0].include_terms == ["saas", "founders"]


@pytest.mark.asyncio
async def test_process_search_plan_marks_empty_query_run_failed() -> None:
    search_run = SearchRun(
        id=uuid4(),
        raw_query="   ",
        normalized_title="",
        requested_by="operator",
        status=SearchRunStatus.DRAFT.value,
        enabled_adapters=["telegram_entity_search"],
        language_hints=[],
        locale_hints=[],
        per_run_candidate_cap=100,
        per_adapter_caps={},
        planner_metadata={},
        ranking_metadata={},
        created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    session = FakeSession(search_run)

    def fake_enqueue(*args, **kwargs) -> QueuedJob:
        raise AssertionError("retrieval should not be enqueued for invalid queries")

    result = await process_search_plan(
        {
            "search_run_id": str(search_run.id),
            "requested_by": "operator",
        },
        session_factory=lambda: session,
        enqueue_search_retrieve_fn=fake_enqueue,
    )

    assert result["status"] == "failed"
    assert search_run.status == SearchRunStatus.FAILED.value
    assert "at least one search term" in (search_run.last_error or "")
    assert search_run.completed_at is not None
    assert session.commits == 1


@pytest.mark.asyncio
async def test_process_search_plan_preserves_hints_and_enqueues_after_commit() -> None:
    search_run = SearchRun(
        id=uuid4(),
        raw_query="Hungarian SaaS founders",
        normalized_title="Hungarian SaaS founders",
        requested_by="operator",
        status=SearchRunStatus.DRAFT.value,
        enabled_adapters=["telegram_entity_search"],
        language_hints=[" hu ", "en", "HU"],
        locale_hints=["hu", "HU"],
        per_run_candidate_cap=100,
        per_adapter_caps={},
        planner_metadata={},
        ranking_metadata={},
        created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    session = FakeSession(search_run)
    enqueued: list[tuple[object, object, object]] = []

    def fake_enqueue(
        search_run_id: object,
        search_query_id: object,
        *,
        requested_by: str | None = None,
    ) -> QueuedJob:
        assert session.commits == 1
        enqueued.append((search_run_id, search_query_id, requested_by))
        return QueuedJob(
            id=f"search.retrieve:{search_run_id}:{search_query_id}",
            type="search.retrieve",
        )

    result = await process_search_plan(
        {
            "search_run_id": str(search_run.id),
            "requested_by": "operator",
        },
        session_factory=lambda: session,
        enqueue_search_retrieve_fn=fake_enqueue,
    )

    assert result["status"] == "planned"
    assert search_run.status == SearchRunStatus.RETRIEVING.value
    assert session.commits == 2
    assert len(session.queries) == 3
    assert len(enqueued) == 3
    assert session.queries[0].language_hint == "hu"
    assert session.queries[0].locale_hint == "HU"
    assert session.queries[0].planner_metadata["language_hints"] == ["hu", "en"]
    assert session.queries[0].planner_metadata["locale_hints"] == ["HU"]
    assert search_run.planner_metadata["include_terms"] == ["hungarian", "saas", "founders"]


@pytest.mark.asyncio
async def test_process_search_plan_fails_run_when_only_deferred_adapters_are_enabled() -> None:
    search_run = SearchRun(
        id=uuid4(),
        raw_query="Hungarian SaaS founders",
        normalized_title="Hungarian SaaS founders",
        requested_by="operator",
        status=SearchRunStatus.DRAFT.value,
        enabled_adapters=["telegram_post_search", "web_search_tme"],
        language_hints=[],
        locale_hints=[],
        per_run_candidate_cap=100,
        per_adapter_caps={},
        planner_metadata={},
        ranking_metadata={},
        created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    session = FakeSession(search_run)
    enqueued: list[object] = []

    def fake_enqueue(*args: object, **kwargs: object) -> QueuedJob:
        enqueued.append((args, kwargs))
        return QueuedJob(id="unexpected", type="search.retrieve")

    result = await process_search_plan(
        {
            "search_run_id": str(search_run.id),
            "requested_by": "operator",
        },
        session_factory=lambda: session,
        enqueue_search_retrieve_fn=fake_enqueue,
    )

    assert result["status"] == "failed"
    assert result["query_ids"] == []
    assert enqueued == []
    assert search_run.status == SearchRunStatus.FAILED.value
    assert search_run.last_error == "All requested search adapters are deferred"
    assert {query.status for query in session.queries} == {"skipped"}


@pytest.mark.asyncio
async def test_process_search_plan_is_idempotent_for_same_run() -> None:
    search_run = SearchRun(
        id=uuid4(),
        raw_query="Hungarian SaaS founders",
        normalized_title="Hungarian SaaS founders",
        requested_by="operator",
        status=SearchRunStatus.DRAFT.value,
        enabled_adapters=["telegram_entity_search"],
        language_hints=["hu"],
        locale_hints=["HU"],
        per_run_candidate_cap=100,
        per_adapter_caps={},
        planner_metadata={},
        ranking_metadata={},
        created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    session = FakeSession(search_run)
    enqueue_calls: list[tuple[object, object, object]] = []

    def fake_enqueue(
        search_run_id: object,
        search_query_id: object,
        *,
        requested_by: str | None = None,
    ) -> QueuedJob:
        enqueue_calls.append((search_run_id, search_query_id, requested_by))
        return QueuedJob(
            id=f"search.retrieve:{search_run_id}:{search_query_id}",
            type="search.retrieve",
        )

    first_result = await process_search_plan(
        {
            "search_run_id": str(search_run.id),
            "requested_by": "operator",
        },
        session_factory=lambda: session,
        enqueue_search_retrieve_fn=fake_enqueue,
    )
    second_result = await process_search_plan(
        {
            "search_run_id": str(search_run.id),
            "requested_by": "operator",
        },
        session_factory=lambda: session,
        enqueue_search_retrieve_fn=fake_enqueue,
    )

    assert first_result["queries_created"] == 3
    assert second_result["queries_created"] == 0
    assert second_result["queries_reused"] == 3
    assert second_result["retrieval_jobs"] == []
    assert len(session.queries) == 3
    assert len(enqueue_calls) == 3


class FakeScalarResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return list(self._items)


class FakeSession:
    def __init__(self, search_run: SearchRun) -> None:
        self.search_run = search_run
        self.queries: list[SearchQuery] = []
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def get(self, model: object, object_id: object) -> object | None:
        if model is SearchRun and object_id == self.search_run.id:
            return self.search_run
        return None

    async def scalars(self, statement: object) -> FakeScalarResult:
        del statement
        return FakeScalarResult(list(self.queries))

    def add(self, item: object) -> None:
        self.added.append(item)
        if isinstance(item, SearchQuery):
            self.queries.append(item)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1
