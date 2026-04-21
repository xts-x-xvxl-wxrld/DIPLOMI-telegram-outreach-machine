from __future__ import annotations

import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from backend.api.schemas import SearchRunCreateRequest
from backend.db.enums import (
    SearchAdapter,
    SearchCandidateStatus,
    SearchEvidenceType,
    SearchQueryStatus,
    SearchReviewAction,
    SearchReviewScope,
    SearchRunStatus,
)
from backend.db.models import (
    SearchCandidate,
    SearchCandidateEvidence,
    SearchQuery,
    SearchReview,
    SearchRun,
)


def test_search_enums_match_contract() -> None:
    assert [item.value for item in SearchAdapter] == ["telegram_entity_search"]
    assert [item.value for item in SearchRunStatus] == [
        "draft",
        "planning",
        "retrieving",
        "ranking",
        "completed",
        "failed",
        "cancelled",
    ]
    assert [item.value for item in SearchQueryStatus] == [
        "pending",
        "running",
        "completed",
        "failed",
        "skipped",
    ]
    assert [item.value for item in SearchCandidateStatus] == [
        "candidate",
        "promoted",
        "rejected",
        "archived",
        "converted_to_seed",
    ]
    assert [item.value for item in SearchReviewAction] == [
        "promote",
        "reject",
        "archive",
        "global_reject",
        "convert_to_seed",
    ]
    assert [item.value for item in SearchReviewScope] == ["run", "global"]
    assert [item.value for item in SearchEvidenceType] == [
        "entity_title_match",
        "entity_username_match",
        "description_match",
        "handle_resolution",
        "manual_seed",
        "linked_discussion",
        "forward_source",
        "telegram_link",
        "mention",
        "post_text_match",
        "web_result",
    ]


def test_search_model_defaults_are_contract_defaults() -> None:
    run_columns = SearchRun.__table__.c
    assert run_columns.status.default.arg == SearchRunStatus.DRAFT.value
    assert run_columns.status.server_default.arg == SearchRunStatus.DRAFT.value
    assert run_columns.per_run_candidate_cap.default.arg == 100
    assert run_columns.per_run_candidate_cap.server_default.arg == "100"

    query_columns = SearchQuery.__table__.c
    assert query_columns.status.default.arg == SearchQueryStatus.PENDING.value
    assert query_columns.planner_source.default.arg == "deterministic_v1"

    candidate_columns = SearchCandidate.__table__.c
    assert candidate_columns.status.default.arg == SearchCandidateStatus.CANDIDATE.value
    assert candidate_columns.score_components.nullable is False

    review_columns = SearchReview.__table__.c
    assert review_columns.scope.default.arg == SearchReviewScope.RUN.value
    assert review_columns["metadata"].nullable is False


def test_search_candidate_allows_unresolved_identity_fields() -> None:
    columns = SearchCandidate.__table__.c

    assert columns.search_run_id.nullable is False
    assert columns.community_id.nullable is True
    assert columns.normalized_username.nullable is True
    assert columns.canonical_url.nullable is True
    assert columns.raw_title.nullable is True
    assert columns.raw_description.nullable is True


def test_search_uniqueness_constraints_and_indexes_are_declared() -> None:
    assert _has_unique_constraint(SearchQuery, ["search_run_id", "adapter", "normalized_query_key"])
    assert _has_index(SearchRun, ["status", "created_at"])
    assert _has_index(SearchRun, ["requested_by", "created_at"])
    assert _has_index(SearchQuery, ["search_run_id", "status"])
    assert _has_index(SearchQuery, ["adapter", "status"])
    assert _has_index(SearchCandidate, ["search_run_id", "status"])
    assert _has_index(SearchCandidate, ["community_id"])
    assert _has_index(SearchCandidate, ["score"])
    assert _has_partial_unique_index(SearchCandidate, ["search_run_id", "community_id"])
    assert _has_partial_unique_index(SearchCandidate, ["search_run_id", "normalized_username"])
    assert _has_partial_unique_index(SearchCandidate, ["search_run_id", "canonical_url"])
    assert _has_index(SearchCandidateEvidence, ["search_candidate_id", "captured_at"])
    assert _has_index(SearchCandidateEvidence, ["search_run_id", "evidence_type"])
    assert _has_index(SearchCandidateEvidence, ["community_id"])
    assert _has_index(SearchReview, ["search_candidate_id", "created_at"])
    assert _has_index(SearchReview, ["search_run_id", "action"])


def test_search_foreign_keys_use_expected_targets_and_cascades() -> None:
    assert _foreign_key_ondelete(SearchQuery, "search_run_id") == "CASCADE"
    assert _foreign_key_ondelete(SearchCandidate, "search_run_id") == "CASCADE"
    assert _foreign_key_ondelete(SearchCandidateEvidence, "search_run_id") == "CASCADE"
    assert _foreign_key_ondelete(SearchCandidateEvidence, "search_candidate_id") == "CASCADE"
    assert _foreign_key_ondelete(SearchCandidateEvidence, "search_query_id") == "SET NULL"
    assert _foreign_key_ondelete(SearchReview, "search_run_id") == "CASCADE"
    assert _foreign_key_ondelete(SearchReview, "search_candidate_id") == "CASCADE"


def test_search_tables_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()

    for model in (
        SearchRun,
        SearchQuery,
        SearchCandidate,
        SearchCandidateEvidence,
        SearchReview,
    ):
        ddl = str(CreateTable(model.__table__).compile(dialect=dialect))
        assert model.__tablename__ in ddl


def test_search_run_create_schema_trims_and_rejects_empty_queries() -> None:
    request = SearchRunCreateRequest(query="  Hungarian SaaS founders  ")

    assert request.query == "Hungarian SaaS founders"
    assert request.enabled_adapters == [SearchAdapter.TELEGRAM_ENTITY_SEARCH]
    assert request.per_run_candidate_cap == 100

    with pytest.raises(ValueError):
        SearchRunCreateRequest(query="   ")


def _has_unique_constraint(model: type[object], column_names: list[str]) -> bool:
    expected = set(column_names)
    return any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == expected
        for constraint in model.__table__.constraints
    )


def _has_index(model: type[object], column_names: list[str]) -> bool:
    return any([column.name for column in index.columns] == column_names for index in model.__table__.indexes)


def _has_partial_unique_index(model: type[object], column_names: list[str]) -> bool:
    return any(
        index.unique
        and [column.name for column in index.columns] == column_names
        and index.dialect_options["postgresql"]["where"] is not None
        for index in model.__table__.indexes
    )


def _foreign_key_ondelete(model: type[object], column_name: str) -> str | None:
    foreign_keys = list(model.__table__.c[column_name].foreign_keys)
    assert len(foreign_keys) == 1
    return foreign_keys[0].ondelete
