from __future__ import annotations

import pytest

from bot.ui import (
    ACTION_APPROVE_COMMUNITY,
    ACTION_COMMUNITY_MEMBERS,
    ACTION_ENGAGEMENT_ACTIONS,
    ACTION_ENGAGEMENT_ADMIN,
    ACTION_ENGAGEMENT_ADMIN_ADVANCED,
    ACTION_ENGAGEMENT_ADMIN_LIMITS,
    ACTION_ENGAGEMENT_APPROVE,
    ACTION_ENGAGEMENT_CANDIDATES,
    ACTION_ENGAGEMENT_DETECT,
    ACTION_ENGAGEMENT_HOME,
    ACTION_ENGAGEMENT_JOIN,
    ACTION_ENGAGEMENT_SETTINGS_OPEN,
    ACTION_ENGAGEMENT_STYLE,
    ACTION_ENGAGEMENT_TARGETS,
    ACTION_ENGAGEMENT_TOPIC_LIST,
    ACTION_SEED_CANDIDATES,
    ENGAGEMENT_MENU_LABEL,
    candidate_actions_markup,
    community_actions_markup,
    engagement_action_pager_markup,
    engagement_candidate_actions_markup,
    engagement_candidate_filter_markup,
    engagement_candidate_pager_markup,
    engagement_candidate_send_markup,
    engagement_admin_home_markup,
    engagement_home_markup,
    engagement_settings_markup,
    engagement_topic_actions_markup,
    engagement_topic_pager_markup,
    encode_callback_data,
    main_menu_markup,
    member_pager_markup,
    parse_callback_data,
    seed_group_pager_markup,
)


def test_encode_and_parse_callback_data_round_trip() -> None:
    data = encode_callback_data(ACTION_SEED_CANDIDATES, "group-1", "10")

    action, parts = parse_callback_data(data)

    assert action == ACTION_SEED_CANDIDATES
    assert parts == ["group-1", "10"]


def test_parse_namespaced_engagement_callback_data_round_trip() -> None:
    data = encode_callback_data(ACTION_ENGAGEMENT_APPROVE, "candidate-1")

    action, parts = parse_callback_data(data)

    assert action == ACTION_ENGAGEMENT_APPROVE
    assert parts == ["candidate-1"]


def test_parse_all_engagement_callback_namespaces() -> None:
    cases = {
        "eng:home": (ACTION_ENGAGEMENT_HOME, []),
        "eng:topic:list:10": ("eng:topic:list", ["10"]),
        "eng:topic:toggle:topic-1:0": ("eng:topic:toggle", ["topic-1", "0"]),
        "eng:set:open:community-1": (ACTION_ENGAGEMENT_SETTINGS_OPEN, ["community-1"]),
        "eng:set:preset:community-1:ready": ("eng:set:preset", ["community-1", "ready"]),
        "eng:join:community-1": (ACTION_ENGAGEMENT_JOIN, ["community-1"]),
        "eng:detect:community-1:60": (ACTION_ENGAGEMENT_DETECT, ["community-1", "60"]),
        "eng:cand:send:candidate-1": ("eng:cand:send", ["candidate-1"]),
        "eng:actions:list:20": (ACTION_ENGAGEMENT_ACTIONS, ["20"]),
    }

    for raw_data, expected in cases.items():
        assert parse_callback_data(raw_data) == expected


def test_encode_callback_data_rejects_oversized_payloads() -> None:
    with pytest.raises(ValueError):
        encode_callback_data("xx", "a" * 70)


def test_engagement_uuid_callback_data_stays_under_telegram_limit() -> None:
    community_id = "12345678-1234-1234-1234-123456789abc"

    data = encode_callback_data("eng:set:preset", community_id, "ready")

    assert len(data) <= 64


def test_main_menu_exposes_engagement_entrypoint() -> None:
    markup = main_menu_markup()
    labels = [button.text for row in markup.keyboard for button in row]

    assert ENGAGEMENT_MENU_LABEL in labels


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
    assert rows[1][1].callback_data == f"{ACTION_ENGAGEMENT_SETTINGS_OPEN}:community-1"


def test_member_pager_markup_pages_members() -> None:
    markup = member_pager_markup("community-1", offset=0, total=25, page_size=10)
    rows = markup.inline_keyboard

    assert rows[0][0].text == "Community"
    assert rows[1][0].callback_data == f"{ACTION_COMMUNITY_MEMBERS}:community-1:10"


def test_engagement_candidate_actions_markup_exposes_review_controls() -> None:
    markup = engagement_candidate_actions_markup("candidate-1")
    rows = markup.inline_keyboard

    assert rows[0][0].callback_data == f"{ACTION_ENGAGEMENT_APPROVE}:candidate-1"
    assert rows[0][1].text == "Reject"
    assert rows[1][0].callback_data == f"{ACTION_ENGAGEMENT_CANDIDATES}:needs_review:0"


def test_engagement_candidate_pager_markup_pages_candidates() -> None:
    markup = engagement_candidate_pager_markup(offset=0, total=12, page_size=5)
    rows = markup.inline_keyboard

    assert rows[0][0].callback_data == f"{ACTION_ENGAGEMENT_CANDIDATES}:needs_review:5"


def test_engagement_home_markup_links_core_surfaces() -> None:
    markup = engagement_home_markup()
    rows = markup.inline_keyboard

    assert rows[0][0].text == "Today"
    assert rows[0][0].callback_data == ACTION_ENGAGEMENT_HOME
    assert rows[1][0].text == "Review replies"
    assert rows[1][0].callback_data == f"{ACTION_ENGAGEMENT_CANDIDATES}:needs_review:0"
    assert rows[1][1].text == "Approved to send"
    assert rows[1][1].callback_data == f"{ACTION_ENGAGEMENT_CANDIDATES}:approved:0"
    assert rows[2][0].text == "Communities"
    assert rows[2][0].callback_data == f"{ACTION_ENGAGEMENT_TARGETS}:0"
    assert rows[2][1].text == "Topics"
    assert rows[2][1].callback_data == f"{ACTION_ENGAGEMENT_TOPIC_LIST}:0"
    assert rows[3][0].text == "Recent actions"
    assert rows[3][0].callback_data == f"{ACTION_ENGAGEMENT_ACTIONS}:0"
    assert rows[4][0].callback_data == ACTION_ENGAGEMENT_ADMIN


def test_engagement_admin_home_markup_links_setup_and_advanced_surfaces() -> None:
    markup = engagement_admin_home_markup()
    rows = markup.inline_keyboard

    assert rows[0][0].text == "Communities"
    assert rows[0][0].callback_data == f"{ACTION_ENGAGEMENT_TARGETS}:0"
    assert rows[0][1].text == "Topics"
    assert rows[0][1].callback_data == f"{ACTION_ENGAGEMENT_TOPIC_LIST}:0"
    assert rows[1][0].text == "Voice rules"
    assert rows[1][0].callback_data == f"{ACTION_ENGAGEMENT_STYLE}:0"
    assert rows[1][1].text == "Limits/accounts"
    assert rows[1][1].callback_data == ACTION_ENGAGEMENT_ADMIN_LIMITS
    assert rows[2][0].text == "Advanced"
    assert rows[2][0].callback_data == ACTION_ENGAGEMENT_ADMIN_ADVANCED


def test_engagement_settings_markup_exposes_presets_and_jobs() -> None:
    markup = engagement_settings_markup("community-1", allow_join=False, allow_post=True)
    rows = markup.inline_keyboard

    assert rows[0][0].callback_data == "eng:set:preset:community-1:off"
    assert rows[1][1].callback_data == "eng:set:preset:community-1:ready"
    assert rows[2][0].callback_data == "eng:set:join:community-1:1"
    assert rows[2][1].callback_data == "eng:set:post:community-1:0"
    assert rows[3][0].callback_data == f"{ACTION_ENGAGEMENT_JOIN}:community-1"
    assert rows[3][1].callback_data == f"{ACTION_ENGAGEMENT_DETECT}:community-1:60"


def test_engagement_topic_markup_pages_and_toggles() -> None:
    pager = engagement_topic_pager_markup(offset=0, total=12, page_size=5)
    actions = engagement_topic_actions_markup("topic-1", active=True)

    assert pager.inline_keyboard[0][0].callback_data == ACTION_ENGAGEMENT_HOME
    assert pager.inline_keyboard[1][0].callback_data == "eng:topic:list:5"
    assert actions.inline_keyboard[0][0].callback_data == "eng:topic:toggle:topic-1:0"


def test_engagement_candidate_send_and_filter_markup() -> None:
    send_markup = engagement_candidate_send_markup("candidate-1")
    filter_markup = engagement_candidate_filter_markup(status="approved")

    assert send_markup.inline_keyboard[0][0].callback_data == "eng:cand:send:candidate-1"
    assert send_markup.inline_keyboard[1][0].callback_data == "eng:cand:list:approved:0"
    assert any(
        button.callback_data == "eng:cand:list:failed:0"
        for row in filter_markup.inline_keyboard
        for button in row
    )


def test_engagement_action_pager_markup_pages_actions() -> None:
    markup = engagement_action_pager_markup(offset=0, total=12, page_size=5)
    rows = markup.inline_keyboard

    assert rows[0][0].callback_data == ACTION_ENGAGEMENT_HOME
    assert rows[1][0].callback_data == f"{ACTION_ENGAGEMENT_ACTIONS}:5"


def test_engagement_action_pager_markup_preserves_community_filter() -> None:
    markup = engagement_action_pager_markup(
        offset=5,
        total=12,
        page_size=5,
        community_id="community-1",
    )
    rows = markup.inline_keyboard

    assert rows[1][0].callback_data == f"{ACTION_ENGAGEMENT_ACTIONS}:community-1:0"
    assert rows[1][1].callback_data == f"{ACTION_ENGAGEMENT_ACTIONS}:community-1:10"
