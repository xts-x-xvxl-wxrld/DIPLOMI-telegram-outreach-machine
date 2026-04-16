from __future__ import annotations

import pytest

from bot.ui import (
    ACTION_APPROVE_COMMUNITY,
    ACTION_COMMUNITY_MEMBERS,
    ACTION_SEED_CANDIDATES,
    candidate_actions_markup,
    community_actions_markup,
    encode_callback_data,
    member_pager_markup,
    parse_callback_data,
    seed_group_pager_markup,
)


def test_encode_and_parse_callback_data_round_trip() -> None:
    data = encode_callback_data(ACTION_SEED_CANDIDATES, "group-1", "10")

    action, parts = parse_callback_data(data)

    assert action == ACTION_SEED_CANDIDATES
    assert parts == ["group-1", "10"]


def test_encode_callback_data_rejects_oversized_payloads() -> None:
    with pytest.raises(ValueError):
        encode_callback_data("xx", "a" * 70)


def test_candidate_actions_markup_exposes_inline_review_controls() -> None:
    markup = candidate_actions_markup("community-1")
    rows = markup.inline_keyboard

    assert rows[0][0].callback_data == f"{ACTION_APPROVE_COMMUNITY}:community-1"
    assert rows[0][1].text == "Reject"
    assert rows[1][0].text == "Community"


def test_seed_group_pager_markup_includes_next_button_when_more_pages_exist() -> None:
    markup = seed_group_pager_markup(
        "group-1",
        offset=0,
        total=12,
        page_size=5,
        action=ACTION_SEED_CANDIDATES,
    )
    rows = markup.inline_keyboard

    assert rows[0][0].text == "Seed Group"
    assert rows[1][0].callback_data == f"{ACTION_SEED_CANDIDATES}:group-1:5"


def test_community_actions_markup_exposes_members_view() -> None:
    markup = community_actions_markup("community-1")
    rows = markup.inline_keyboard

    assert rows[1][0].callback_data == f"{ACTION_COMMUNITY_MEMBERS}:community-1:0"


def test_member_pager_markup_pages_members() -> None:
    markup = member_pager_markup("community-1", offset=0, total=25, page_size=10)
    rows = markup.inline_keyboard

    assert rows[0][0].text == "Community"
    assert rows[1][0].callback_data == f"{ACTION_COMMUNITY_MEMBERS}:community-1:10"
