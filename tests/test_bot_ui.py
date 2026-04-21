from __future__ import annotations

import pytest

from bot.ui import (
    ACTION_APPROVE_COMMUNITY,
    ACTION_COMMUNITY_MEMBERS,
    ACTION_CONFIG_EDIT_CANCEL,
    ACTION_CONFIG_EDIT_SAVE,
    ACTION_DISC_ACTIVITY,
    ACTION_DISC_ALL,
    ACTION_DISC_ATTENTION,
    ACTION_DISC_HELP,
    ACTION_DISC_HOME,
    ACTION_DISC_REVIEW,
    ACTION_DISC_START,
    ACTION_DISC_WATCHING,
    ACTION_ENGAGEMENT_ACTIONS,
    ACTION_ENGAGEMENT_ADMIN,
    ACTION_ENGAGEMENT_ADMIN_ADVANCED,
    ACTION_ENGAGEMENT_ADMIN_LIMITS,
    ACTION_ENGAGEMENT_APPROVE,
    ACTION_ENGAGEMENT_CANDIDATES,
    ACTION_ENGAGEMENT_CANDIDATE_EDIT,
    ACTION_ENGAGEMENT_CANDIDATE_EXPIRE,
    ACTION_ENGAGEMENT_CANDIDATE_OPEN,
    ACTION_ENGAGEMENT_CANDIDATE_RETRY,
    ACTION_ENGAGEMENT_CANDIDATE_REVISIONS,
    ACTION_ENGAGEMENT_DETECT,
    ACTION_ENGAGEMENT_HOME,
    ACTION_ENGAGEMENT_JOIN,
    ACTION_ENGAGEMENT_SETTINGS_OPEN,
    ACTION_ENGAGEMENT_STYLE,
    ACTION_ENGAGEMENT_TARGET_APPROVE,
    ACTION_ENGAGEMENT_TARGET_DETECT,
    ACTION_ENGAGEMENT_TARGET_JOIN,
    ACTION_ENGAGEMENT_TARGET_OPEN,
    ACTION_ENGAGEMENT_TARGET_PERMISSION,
    ACTION_ENGAGEMENT_TARGETS,
    ACTION_ENGAGEMENT_TOPIC_LIST,
    ACTION_OP_ACCOUNTS,
    ACTION_OP_DISCOVERY,
    ACTION_OP_HELP,
    ACTION_OP_HOME,
    ACTION_SEED_CANDIDATES,
    ENGAGEMENT_MENU_LABEL,
    candidate_actions_markup,
    community_actions_markup,
    config_edit_confirmation_markup,
    discovery_cockpit_markup,
    engagement_action_pager_markup,
    engagement_candidate_actions_markup,
    engagement_candidate_detail_markup,
    engagement_candidate_filter_markup,
    engagement_candidate_pager_markup,
    engagement_candidate_revisions_markup,
    engagement_candidate_send_markup,
    engagement_admin_home_markup,
    engagement_home_markup,
    engagement_settings_markup,
    engagement_target_actions_markup,
    engagement_target_list_markup,
    engagement_topic_actions_markup,
    engagement_topic_pager_markup,
    encode_callback_data,
    main_menu_markup,
    member_pager_markup,
    operator_cockpit_markup,
    parse_callback_data,
    seed_group_pager_markup,
)


def _buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def _callbacks(markup) -> list[str]:
    return [button.callback_data for button in _buttons(markup)]


def _labels(markup) -> list[str]:
    return [button.text for button in _buttons(markup)]


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
        "eng:admin:to:target-1": (ACTION_ENGAGEMENT_TARGET_OPEN, ["target-1"]),
        "eng:admin:tp:target-1:p:1": (ACTION_ENGAGEMENT_TARGET_PERMISSION, ["target-1", "p", "1"]),
        "eng:admin:tj:target-1": (ACTION_ENGAGEMENT_TARGET_JOIN, ["target-1"]),
        "eng:admin:td:target-1:60": (ACTION_ENGAGEMENT_TARGET_DETECT, ["target-1", "60"]),
        "eng:cand:send:candidate-1": ("eng:cand:send", ["candidate-1"]),
        "eng:edit:save": (ACTION_CONFIG_EDIT_SAVE, []),
        "eng:edit:cancel": (ACTION_CONFIG_EDIT_CANCEL, []),
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


def test_config_edit_callback_data_stays_under_telegram_limit() -> None:
    assert len(ACTION_CONFIG_EDIT_SAVE) <= 64
    assert len(ACTION_CONFIG_EDIT_CANCEL) <= 64


def test_config_edit_confirmation_markup_exposes_save_and_cancel() -> None:
    markup = config_edit_confirmation_markup()
    rows = markup.inline_keyboard

    assert rows[0][0].callback_data == ACTION_CONFIG_EDIT_SAVE
    assert rows[0][1].callback_data == ACTION_CONFIG_EDIT_CANCEL


def test_engagement_target_permission_callback_data_stays_under_telegram_limit() -> None:
    target_id = "12345678-1234-1234-1234-123456789abc"

    data = encode_callback_data(ACTION_ENGAGEMENT_TARGET_PERMISSION, target_id, "p", "1")

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
    callbacks = _callbacks(markup)

    assert f"{ACTION_COMMUNITY_MEMBERS}:community-1:10" in callbacks
    assert "Back" in _labels(markup)
    assert ACTION_OP_HOME in callbacks


def test_engagement_candidate_actions_markup_exposes_review_controls() -> None:
    markup = engagement_candidate_actions_markup("candidate-1")
    rows = markup.inline_keyboard

    assert rows[0][0].callback_data == f"{ACTION_ENGAGEMENT_CANDIDATE_OPEN}:candidate-1"
    assert rows[1][0].callback_data == f"{ACTION_ENGAGEMENT_CANDIDATE_EDIT}:candidate-1"
    assert rows[1][1].callback_data == f"{ACTION_ENGAGEMENT_APPROVE}:candidate-1"
    assert rows[1][2].text == "Reject"
    assert rows[2][0].callback_data == f"{ACTION_ENGAGEMENT_CANDIDATES}:needs_review:0"


def test_engagement_candidate_detail_markup_is_state_aware() -> None:
    approved = engagement_candidate_detail_markup("candidate-1", status="approved")
    failed = engagement_candidate_detail_markup("candidate-2", status="failed")
    sent = engagement_candidate_detail_markup("candidate-3", status="sent")

    assert "eng:cand:send:candidate-1" in _callbacks(approved)
    assert f"{ACTION_ENGAGEMENT_CANDIDATE_EXPIRE}:candidate-1" in _callbacks(approved)
    assert f"{ACTION_ENGAGEMENT_CANDIDATE_RETRY}:candidate-2" in _callbacks(failed)
    assert f"{ACTION_ENGAGEMENT_CANDIDATE_REVISIONS}:candidate-3" in _callbacks(sent)
    assert "eng:cand:send:candidate-3" not in _callbacks(sent)


def test_engagement_candidate_revisions_markup_only_reopens_candidate_detail() -> None:
    markup = engagement_candidate_revisions_markup("candidate-1")

    assert f"{ACTION_ENGAGEMENT_CANDIDATE_OPEN}:candidate-1" in _callbacks(markup)
    assert f"{ACTION_ENGAGEMENT_CANDIDATE_EDIT}:candidate-1" not in _callbacks(markup)
    assert "eng:cand:send:candidate-1" not in _callbacks(markup)


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


def test_engagement_target_list_markup_filters_and_pages() -> None:
    markup = engagement_target_list_markup(status="approved", offset=5, total=12, page_size=5)
    rows = markup.inline_keyboard
    callbacks = _callbacks(markup)

    assert rows[0][0].text == "Add target"
    assert rows[1][0].callback_data == f"{ACTION_ENGAGEMENT_TARGETS}:all:0"
    assert rows[1][3].callback_data == f"{ACTION_ENGAGEMENT_TARGETS}:approved:0"
    assert rows[2][2].callback_data == f"{ACTION_ENGAGEMENT_TARGETS}:archived:0"
    assert f"{ACTION_ENGAGEMENT_TARGETS}:approved:0" in callbacks
    assert f"{ACTION_ENGAGEMENT_TARGETS}:approved:10" in callbacks
    assert ACTION_ENGAGEMENT_ADMIN in callbacks
    assert ACTION_OP_HOME in callbacks


def test_engagement_target_actions_markup_exposes_safe_target_controls() -> None:
    pending = engagement_target_actions_markup("target-1", status="pending")
    approved = engagement_target_actions_markup(
        "target-2",
        status="approved",
        allow_join=True,
        allow_detect=True,
        allow_post=False,
    )

    pending_callbacks = [
        button.callback_data for row in pending.inline_keyboard for button in row
    ]
    approved_callbacks = [
        button.callback_data for row in approved.inline_keyboard for button in row
    ]
    assert f"{ACTION_ENGAGEMENT_TARGET_APPROVE}:target-1" not in pending_callbacks
    assert f"{ACTION_ENGAGEMENT_TARGET_OPEN}:target-1" in pending_callbacks
    assert "eng:admin:tr:target-1" in pending_callbacks
    assert f"{ACTION_ENGAGEMENT_TARGET_PERMISSION}:target-2:p:1" in approved_callbacks
    assert f"{ACTION_ENGAGEMENT_TARGET_JOIN}:target-2" in approved_callbacks
    assert f"{ACTION_ENGAGEMENT_TARGET_DETECT}:target-2:60" in approved_callbacks


def test_engagement_topic_markup_pages_and_toggles() -> None:
    pager = engagement_topic_pager_markup(offset=0, total=12, page_size=5)
    actions = engagement_topic_actions_markup("topic-1", active=True)

    assert ACTION_ENGAGEMENT_HOME in _callbacks(pager)
    assert "eng:topic:list:5" in _callbacks(pager)
    assert actions.inline_keyboard[0][0].callback_data == "eng:topic:toggle:topic-1:0"
    assert "eng:topic:list:0" in _callbacks(actions)
    assert ACTION_OP_HOME in _callbacks(actions)


def test_engagement_candidate_send_and_filter_markup() -> None:
    send_markup = engagement_candidate_send_markup("candidate-1")
    filter_markup = engagement_candidate_filter_markup(status="approved")

    assert send_markup.inline_keyboard[0][0].callback_data == "eng:cand:send:candidate-1"
    assert send_markup.inline_keyboard[1][0].callback_data == "eng:cand:open:candidate-1"
    assert send_markup.inline_keyboard[2][0].callback_data == "eng:cand:list:approved:0"
    assert any(
        button.callback_data == "eng:cand:list:failed:0"
        for row in filter_markup.inline_keyboard
        for button in row
    )


def test_engagement_action_pager_markup_pages_actions() -> None:
    markup = engagement_action_pager_markup(offset=0, total=12, page_size=5)
    callbacks = _callbacks(markup)

    assert ACTION_ENGAGEMENT_HOME in callbacks
    assert f"{ACTION_ENGAGEMENT_ACTIONS}:5" in callbacks
    assert ACTION_OP_HOME in callbacks


def test_engagement_action_pager_markup_preserves_community_filter() -> None:
    markup = engagement_action_pager_markup(
        offset=5,
        total=12,
        page_size=5,
        community_id="community-1",
    )
    callbacks = _callbacks(markup)

    assert f"{ACTION_ENGAGEMENT_ACTIONS}:community-1:0" in callbacks
    assert f"{ACTION_ENGAGEMENT_ACTIONS}:community-1:10" in callbacks


# ---------------------------------------------------------------------------
# Operator cockpit UI
# ---------------------------------------------------------------------------


def test_operator_cockpit_markup_exposes_four_top_level_buttons() -> None:
    markup = operator_cockpit_markup()
    rows = markup.inline_keyboard

    all_callbacks = [button.callback_data for row in rows for button in row]
    assert ACTION_OP_DISCOVERY in all_callbacks
    assert ACTION_ENGAGEMENT_HOME in all_callbacks
    assert ACTION_OP_ACCOUNTS in all_callbacks
    assert ACTION_OP_HELP in all_callbacks


def test_operator_cockpit_markup_button_labels() -> None:
    markup = operator_cockpit_markup()
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "Discovery" in labels
    assert "Engagement" in labels
    assert "Accounts" in labels
    assert "Help" in labels


def test_operator_cockpit_callback_data_stays_under_telegram_limit() -> None:
    for action in (ACTION_OP_HOME, ACTION_OP_DISCOVERY, ACTION_OP_ACCOUNTS, ACTION_OP_HELP):
        assert len(action) <= 64


def test_discovery_cockpit_markup_exposes_six_navigation_entries_and_back() -> None:
    markup = discovery_cockpit_markup()
    all_callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]

    assert ACTION_DISC_START in all_callbacks
    assert ACTION_DISC_ATTENTION in all_callbacks
    assert ACTION_DISC_REVIEW in all_callbacks
    assert ACTION_DISC_WATCHING in all_callbacks
    assert ACTION_DISC_ACTIVITY in all_callbacks
    assert ACTION_DISC_HELP in all_callbacks
    assert ACTION_OP_HOME in all_callbacks


def test_discovery_cockpit_markup_button_labels() -> None:
    markup = discovery_cockpit_markup()
    labels = _labels(markup)

    assert "Start search" in labels
    assert "Needs attention" in labels
    assert "Review communities" in labels
    assert "Watching" in labels
    assert "Recent activity" in labels
    assert "Help" in labels
    assert "Home" in labels


def test_navigation_footer_adds_back_and_home_buttons_to_child_pages() -> None:
    markup = community_actions_markup("community-1")
    callbacks = _callbacks(markup)
    labels = _labels(markup)

    assert "Back" in labels
    assert "Home" in labels
    assert ACTION_DISC_HOME in callbacks
    assert ACTION_OP_HOME in callbacks


def test_discovery_cockpit_callback_data_stays_under_telegram_limit() -> None:
    for action in (
        ACTION_DISC_HOME,
        ACTION_DISC_START,
        ACTION_DISC_ATTENTION,
        ACTION_DISC_REVIEW,
        ACTION_DISC_WATCHING,
        ACTION_DISC_ACTIVITY,
        ACTION_DISC_HELP,
        ACTION_DISC_ALL,
    ):
        assert len(action) <= 64


# ---------------------------------------------------------------------------
# op:* and disc:* callback parser
# ---------------------------------------------------------------------------


def test_parse_op_callbacks() -> None:
    cases = {
        "op:home": (ACTION_OP_HOME, []),
        "op:discovery": (ACTION_OP_DISCOVERY, []),
        "op:accounts": (ACTION_OP_ACCOUNTS, []),
        "op:help": (ACTION_OP_HELP, []),
    }
    for raw_data, expected in cases.items():
        assert parse_callback_data(raw_data) == expected


def test_parse_disc_callbacks() -> None:
    cases = {
        "disc:home": (ACTION_DISC_HOME, []),
        "disc:start": (ACTION_DISC_START, []),
        "disc:attention": (ACTION_DISC_ATTENTION, []),
        "disc:review": (ACTION_DISC_REVIEW, []),
        "disc:watching": (ACTION_DISC_WATCHING, []),
        "disc:activity": (ACTION_DISC_ACTIVITY, []),
        "disc:help": (ACTION_DISC_HELP, []),
        "disc:all": (ACTION_DISC_ALL, []),
        "disc:search:sg-1": ("disc:search", ["sg-1"]),
        "disc:examples:sg-1:10": ("disc:examples", ["sg-1", "10"]),
        "disc:watch:comm-1": ("disc:watch", ["comm-1"]),
        "disc:skip:comm-1": ("disc:skip", ["comm-1"]),
    }
    for raw_data, expected in cases.items():
        assert parse_callback_data(raw_data) == expected


def test_parse_op_disc_do_not_break_eng_namespace() -> None:
    assert parse_callback_data("eng:home") == (ACTION_ENGAGEMENT_HOME, [])
    assert parse_callback_data("eng:cand:list:needs_review:0") == ("eng:cand:list", ["needs_review", "0"])
    assert parse_callback_data("eng:admin:to:target-1") == (ACTION_ENGAGEMENT_TARGET_OPEN, ["target-1"])
