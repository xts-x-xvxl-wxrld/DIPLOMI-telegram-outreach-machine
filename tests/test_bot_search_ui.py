from __future__ import annotations

from bot.ui import (
    ACTION_SEARCH_CONVERT,
    ACTION_SEARCH_REVIEW,
    ACTION_SEARCH_RUN_CANDIDATES,
    parse_callback_data,
    search_candidate_actions_markup,
    search_candidate_pager_markup,
)


def test_search_candidate_actions_include_review_and_conversion_for_promoted() -> None:
    markup = search_candidate_actions_markup("cand-1", status="promoted")
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]

    assert f"{ACTION_SEARCH_REVIEW}:cand-1:promote" in callbacks
    assert f"{ACTION_SEARCH_REVIEW}:cand-1:reject" in callbacks
    assert f"{ACTION_SEARCH_REVIEW}:cand-1:archive" in callbacks
    assert f"{ACTION_SEARCH_CONVERT}:cand-1" in callbacks


def test_search_candidate_pager_uses_short_callback_data() -> None:
    markup = search_candidate_pager_markup("run-1", offset=0, total=12, page_size=5)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]

    assert f"{ACTION_SEARCH_RUN_CANDIDATES}:run-1:5" in callbacks
    for callback in callbacks:
        assert len(callback) <= 64


def test_search_callback_data_round_trips() -> None:
    action, parts = parse_callback_data(f"{ACTION_SEARCH_REVIEW}:cand-1:promote")

    assert action == ACTION_SEARCH_REVIEW
    assert parts == ["cand-1", "promote"]
