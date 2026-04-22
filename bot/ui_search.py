from __future__ import annotations

from .ui_common import (
    ACTION_DISC_HOME,
    ACTION_SEARCH_CONVERT,
    ACTION_SEARCH_RERANK,
    ACTION_SEARCH_REVIEW,
    ACTION_SEARCH_RUN_CANDIDATES,
    ACTION_SEARCH_RUN_OPEN,
    _button,
    _inline_markup,
    _pager_row,
    _with_navigation,
)


def search_run_actions_markup(search_run_id: str):
    rows = [
        [_button("Open", ACTION_SEARCH_RUN_OPEN, search_run_id)],
        [_button("Candidates", ACTION_SEARCH_RUN_CANDIDATES, search_run_id, "0")],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_HOME))


def search_run_detail_markup(search_run_id: str):
    rows = [
        [_button("Candidates", ACTION_SEARCH_RUN_CANDIDATES, search_run_id, "0")],
        [_button("Rerank", ACTION_SEARCH_RERANK, search_run_id)],
        [_button("Refresh", ACTION_SEARCH_RUN_OPEN, search_run_id)],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_HOME))


def search_candidate_actions_markup(candidate_id: str, *, status: str | None = None):
    rows = [
        [
            _button("Promote", ACTION_SEARCH_REVIEW, candidate_id, "promote"),
            _button("Reject", ACTION_SEARCH_REVIEW, candidate_id, "reject"),
        ],
        [_button("Archive", ACTION_SEARCH_REVIEW, candidate_id, "archive")],
    ]
    if status == "promoted":
        rows.append([_button("Convert to seed", ACTION_SEARCH_CONVERT, candidate_id)])
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_HOME))


def search_candidate_review_markup(candidate_id: str, *, status: str | None = None):
    rows = []
    if status == "promoted":
        rows.append([_button("Convert to seed", ACTION_SEARCH_CONVERT, candidate_id)])
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_HOME))


def search_candidate_pager_markup(
    search_run_id: str,
    *,
    offset: int,
    total: int,
    page_size: int,
):
    rows = [[_button("Search run", ACTION_SEARCH_RUN_OPEN, search_run_id)]]
    pager_row = _pager_row(
        action=ACTION_SEARCH_RUN_CANDIDATES,
        item_id=search_run_id,
        offset=offset,
        total=total,
        page_size=page_size,
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(_with_navigation(rows, back_action=ACTION_SEARCH_RUN_OPEN, back_parts=[search_run_id]))


def search_seed_conversion_markup(seed_group_id: str | None):
    rows = []
    if seed_group_id:
        from .ui_common import ACTION_OPEN_SEED_GROUP

        rows.append([_button("Seed group", ACTION_OPEN_SEED_GROUP, seed_group_id)])
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_HOME))
