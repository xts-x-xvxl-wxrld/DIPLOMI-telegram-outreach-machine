from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


SEEDS_MENU_LABEL = "Seed Groups"
ENGAGEMENT_MENU_LABEL = "Engagement"
ACCOUNTS_MENU_LABEL = "Accounts"
HELP_MENU_LABEL = "Help"

# Operator cockpit callbacks
ACTION_OP_HOME = "op:home"
ACTION_OP_DISCOVERY = "op:discovery"
ACTION_OP_ACCOUNTS = "op:accounts"
ACTION_OP_HELP = "op:help"

# Discovery cockpit callbacks
ACTION_DISC_HOME = "disc:home"
ACTION_DISC_START = "disc:start"
ACTION_DISC_ATTENTION = "disc:attention"
ACTION_DISC_REVIEW = "disc:review"
ACTION_DISC_WATCHING = "disc:watching"
ACTION_DISC_ACTIVITY = "disc:activity"
ACTION_DISC_HELP = "disc:help"
ACTION_DISC_ALL = "disc:all"
ACTION_DISC_SEARCH = "disc:search"
ACTION_DISC_EXAMPLES = "disc:examples"
ACTION_DISC_CHECK = "disc:check"
ACTION_DISC_CANDIDATES = "disc:candidates"
ACTION_DISC_WATCH = "disc:watch"
ACTION_DISC_SKIP = "disc:skip"

ACTION_OPEN_SEED_GROUP = "sg"
ACTION_RESOLVE_SEED_GROUP = "sr"
ACTION_SEED_CHANNELS = "sl"
ACTION_SEED_CANDIDATES = "sc"
ACTION_OPEN_COMMUNITY = "cm"
ACTION_APPROVE_COMMUNITY = "ca"
ACTION_REJECT_COMMUNITY = "cr"
ACTION_SNAPSHOT_COMMUNITY = "sn"
ACTION_COMMUNITY_MEMBERS = "mb"
ACTION_JOB_STATUS = "jb"
ACTION_ENGAGEMENT_HOME = "eng:home"
ACTION_ENGAGEMENT_CANDIDATES = "eng:cand:list"
ACTION_ENGAGEMENT_APPROVE = "eng:cand:approve"
ACTION_ENGAGEMENT_REJECT = "eng:cand:reject"
ACTION_ENGAGEMENT_SEND = "eng:cand:send"
ACTION_ENGAGEMENT_CANDIDATE_OPEN = "eng:cand:open"
ACTION_ENGAGEMENT_CANDIDATE_EDIT = "eng:cand:edit"
ACTION_ENGAGEMENT_CANDIDATE_REVISIONS = "eng:cand:rev"
ACTION_ENGAGEMENT_CANDIDATE_EXPIRE = "eng:cand:exp"
ACTION_ENGAGEMENT_CANDIDATE_RETRY = "eng:cand:retry"
ACTION_ENGAGEMENT_TOPIC_LIST = "eng:topic:list"
ACTION_ENGAGEMENT_TOPIC_OPEN = "eng:topic:open"
ACTION_ENGAGEMENT_TOPIC_TOGGLE = "eng:topic:toggle"
ACTION_ENGAGEMENT_TOPIC_EDIT = "eng:topic:edit"
ACTION_ENGAGEMENT_TOPIC_EXAMPLE_ADD = "eng:topic:addx"
ACTION_ENGAGEMENT_TOPIC_EXAMPLE_REMOVE = "eng:topic:rmx"
ACTION_ENGAGEMENT_SETTINGS_OPEN = "eng:set:open"
ACTION_ENGAGEMENT_SETTINGS_PRESET = "eng:set:preset"
ACTION_ENGAGEMENT_SETTINGS_JOIN = "eng:set:join"
ACTION_ENGAGEMENT_SETTINGS_POST = "eng:set:post"
ACTION_ENGAGEMENT_SETTINGS_EDIT = "eng:set:e"
ACTION_ENGAGEMENT_ACCOUNT_CONFIRM = "eng:set:acctc"
ACTION_ENGAGEMENT_ACCOUNT_CANCEL = "eng:set:acctx"
ACTION_ENGAGEMENT_JOIN = "eng:join"
ACTION_ENGAGEMENT_DETECT = "eng:detect"
ACTION_ENGAGEMENT_ACTIONS = "eng:actions:list"
ACTION_ENGAGEMENT_ADMIN = "eng:admin:home"
ACTION_ENGAGEMENT_TARGETS = "eng:admin:tgt"
ACTION_ENGAGEMENT_TARGET_ADD = "eng:admin:tna"
ACTION_ENGAGEMENT_TARGET_OPEN = "eng:admin:to"
ACTION_ENGAGEMENT_TARGET_APPROVE = "eng:admin:ta"
ACTION_ENGAGEMENT_TARGET_APPROVE_CONFIRM = "eng:admin:tac"
ACTION_ENGAGEMENT_TARGET_RESOLVE = "eng:admin:tr"
ACTION_ENGAGEMENT_TARGET_REJECT = "eng:admin:tx"
ACTION_ENGAGEMENT_TARGET_ARCHIVE = "eng:admin:tz"
ACTION_ENGAGEMENT_TARGET_PERMISSION = "eng:admin:tp"
ACTION_ENGAGEMENT_TARGET_PERMISSION_CONFIRM = "eng:admin:tpc"
ACTION_ENGAGEMENT_TARGET_EDIT = "eng:admin:te"
ACTION_ENGAGEMENT_TARGET_JOIN = "eng:admin:tj"
ACTION_ENGAGEMENT_TARGET_DETECT = "eng:admin:td"
ACTION_ENGAGEMENT_PROMPTS = "eng:admin:pr"
ACTION_ENGAGEMENT_PROMPT_OPEN = "eng:admin:po"
ACTION_ENGAGEMENT_PROMPT_PREVIEW = "eng:admin:pp"
ACTION_ENGAGEMENT_PROMPT_VERSIONS = "eng:admin:pv"
ACTION_ENGAGEMENT_PROMPT_EDIT = "eng:admin:pe"
ACTION_ENGAGEMENT_PROMPT_CREATE = "eng:admin:pc"
ACTION_ENGAGEMENT_PROMPT_DUPLICATE = "eng:admin:pd"
ACTION_ENGAGEMENT_PROMPT_ACTIVATE = "eng:admin:pa"
ACTION_ENGAGEMENT_PROMPT_ACTIVATE_CONFIRM = "eng:admin:pac"
ACTION_ENGAGEMENT_PROMPT_ROLLBACK = "eng:admin:prb"
ACTION_ENGAGEMENT_PROMPT_ROLLBACK_CONFIRM = "eng:admin:prbc"
ACTION_ENGAGEMENT_STYLE = "eng:admin:sr"
ACTION_ENGAGEMENT_STYLE_CREATE = "eng:admin:src"
ACTION_ENGAGEMENT_STYLE_OPEN = "eng:admin:sro"
ACTION_ENGAGEMENT_STYLE_EDIT = "eng:admin:sre"
ACTION_ENGAGEMENT_STYLE_TOGGLE = "eng:admin:srt"
ACTION_ENGAGEMENT_ADMIN_LIMITS = "eng:admin:lim"
ACTION_ENGAGEMENT_ADMIN_ADVANCED = "eng:admin:adv"
ACTION_CONFIG_EDIT_SAVE = "eng:edit:save"
ACTION_CONFIG_EDIT_CANCEL = "eng:edit:cancel"


@dataclass(frozen=True)
class _FallbackInlineKeyboardButton:
    text: str
    callback_data: str


@dataclass(frozen=True)
class _FallbackInlineKeyboardMarkup:
    inline_keyboard: Sequence[Sequence[object]]


@dataclass(frozen=True)
class _FallbackKeyboardButton:
    text: str


@dataclass(frozen=True)
class _FallbackReplyKeyboardMarkup:
    keyboard: Sequence[Sequence[object]]
    resize_keyboard: bool
    is_persistent: bool


@dataclass(frozen=True)
class _FallbackReplyKeyboardRemove:
    pass


def operator_cockpit_markup():
    return _inline_markup(
        [
            [_button("Discovery", ACTION_OP_DISCOVERY)],
            [_button("Engagement", ACTION_ENGAGEMENT_HOME)],
            [_button("Accounts", ACTION_OP_ACCOUNTS)],
            [_button("Help", ACTION_OP_HELP)],
        ]
    )


def discovery_cockpit_markup():
    rows = [
        [_button("Start search", ACTION_DISC_START)],
        [_button("Needs attention", ACTION_DISC_ATTENTION)],
        [_button("Review communities", ACTION_DISC_REVIEW)],
        [_button("Watching", ACTION_DISC_WATCHING)],
        [_button("Recent activity", ACTION_DISC_ACTIVITY)],
        [_button("Help", ACTION_DISC_HELP)],
    ]
    return _inline_markup(_with_navigation(rows))


def discovery_seeds_markup():
    return _inline_markup(_with_navigation([], back_action=ACTION_DISC_HOME))


def reply_keyboard_remove():
    try:
        from telegram import ReplyKeyboardRemove
    except ImportError:
        return _FallbackReplyKeyboardRemove()
    return ReplyKeyboardRemove()


def main_menu_markup():
    KeyboardButton, ReplyKeyboardMarkup = _keyboard_types()

    keyboard = [
        [KeyboardButton(SEEDS_MENU_LABEL), KeyboardButton(ENGAGEMENT_MENU_LABEL)],
        [KeyboardButton(ACCOUNTS_MENU_LABEL)],
        [KeyboardButton(HELP_MENU_LABEL)],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )


def seed_group_actions_markup(seed_group_id: str):
    rows = [
        [_button("Open", ACTION_OPEN_SEED_GROUP, seed_group_id)],
        [
            _button("Resolve", ACTION_RESOLVE_SEED_GROUP, seed_group_id),
            _button("Channels", ACTION_SEED_CHANNELS, seed_group_id, "0"),
        ],
        [_button("Candidates", ACTION_SEED_CANDIDATES, seed_group_id, "0")],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_ALL))


def seed_group_pager_markup(
    seed_group_id: str,
    *,
    offset: int,
    total: int,
    page_size: int,
    action: str,
):
    rows = [[_button("Seed Group", ACTION_OPEN_SEED_GROUP, seed_group_id)]]
    pager_row = _pager_row(
        action=action,
        item_id=seed_group_id,
        offset=offset,
        total=total,
        page_size=page_size,
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_OPEN_SEED_GROUP, back_parts=[seed_group_id])
    )


def candidate_actions_markup(community_id: str):
    rows = [
        [
            _button("Approve", ACTION_APPROVE_COMMUNITY, community_id),
            _button("Reject", ACTION_REJECT_COMMUNITY, community_id),
        ],
        [_button("Community", ACTION_OPEN_COMMUNITY, community_id)],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_REVIEW))


def engagement_candidate_actions_markup(candidate_id: str):
    rows = [
        [_button("Open", ACTION_ENGAGEMENT_CANDIDATE_OPEN, candidate_id)],
        [
            _button("Edit", ACTION_ENGAGEMENT_CANDIDATE_EDIT, candidate_id),
            _button("Approve", ACTION_ENGAGEMENT_APPROVE, candidate_id),
            _button("Reject", ACTION_ENGAGEMENT_REJECT, candidate_id),
        ],
        [_button("More replies", ACTION_ENGAGEMENT_CANDIDATES, "needs_review", "0")],
    ]
    return _inline_markup(
        _with_navigation(
            rows,
            back_action=ACTION_ENGAGEMENT_CANDIDATES,
            back_parts=["needs_review", "0"],
        )
    )


def engagement_candidate_send_markup(candidate_id: str):
    rows = [
        [_button("Queue send", ACTION_ENGAGEMENT_SEND, candidate_id)],
        [_button("Open", ACTION_ENGAGEMENT_CANDIDATE_OPEN, candidate_id)],
        [_button("Approved replies", ACTION_ENGAGEMENT_CANDIDATES, "approved", "0")],
    ]
    return _inline_markup(
        _with_navigation(
            rows,
            back_action=ACTION_ENGAGEMENT_CANDIDATES,
            back_parts=["approved", "0"],
        )
    )


def engagement_candidate_detail_markup(candidate_id: str, *, status: str):
    rows = [[_button("Revisions", ACTION_ENGAGEMENT_CANDIDATE_REVISIONS, candidate_id)]]
    if status == "needs_review":
        rows.insert(
            0,
            [
                _button("Edit", ACTION_ENGAGEMENT_CANDIDATE_EDIT, candidate_id),
                _button("Approve", ACTION_ENGAGEMENT_APPROVE, candidate_id),
                _button("Reject", ACTION_ENGAGEMENT_REJECT, candidate_id),
            ],
        )
        rows.append([_button("Expire", ACTION_ENGAGEMENT_CANDIDATE_EXPIRE, candidate_id)])
    elif status == "approved":
        rows.insert(0, [_button("Queue send", ACTION_ENGAGEMENT_SEND, candidate_id)])
        rows.insert(
            1,
            [
                _button("Edit", ACTION_ENGAGEMENT_CANDIDATE_EDIT, candidate_id),
                _button("Reject", ACTION_ENGAGEMENT_REJECT, candidate_id),
            ],
        )
        rows.append([_button("Expire", ACTION_ENGAGEMENT_CANDIDATE_EXPIRE, candidate_id)])
    elif status == "failed":
        rows.insert(
            0,
            [
                _button("Retry", ACTION_ENGAGEMENT_CANDIDATE_RETRY, candidate_id),
                _button("Edit", ACTION_ENGAGEMENT_CANDIDATE_EDIT, candidate_id),
                _button("Reject", ACTION_ENGAGEMENT_REJECT, candidate_id),
            ],
        )
        rows.append([_button("Expire", ACTION_ENGAGEMENT_CANDIDATE_EXPIRE, candidate_id)])
    return _inline_markup(
        _with_navigation(
            rows,
            back_action=ACTION_ENGAGEMENT_CANDIDATES,
            back_parts=[status if status in {"approved", "failed", "sent", "rejected"} else "needs_review", "0"],
        )
    )


def engagement_candidate_revisions_markup(candidate_id: str):
    rows = [[_button("Open", ACTION_ENGAGEMENT_CANDIDATE_OPEN, candidate_id)]]
    return _inline_markup(
        _with_navigation(
            rows,
            back_action=ACTION_ENGAGEMENT_CANDIDATES,
            back_parts=["needs_review", "0"],
        )
    )


def engagement_candidate_pager_markup(
    *,
    offset: int,
    total: int,
    page_size: int,
    status: str = "needs_review",
):
    buttons = _offset_pager_row(
        action=ACTION_ENGAGEMENT_CANDIDATES,
        offset=offset,
        total=total,
        page_size=page_size,
        prefix_parts=[status],
    )
    rows = []
    if buttons:
        rows.append(buttons)
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_home_markup(*, show_admin: bool = True):
    rows = [
        [_button("Today", ACTION_ENGAGEMENT_HOME)],
        [
            _button("Review replies", ACTION_ENGAGEMENT_CANDIDATES, "needs_review", "0"),
            _button("Approved to send", ACTION_ENGAGEMENT_CANDIDATES, "approved", "0"),
        ],
        [
            _button("Communities", ACTION_ENGAGEMENT_TARGETS, "0"),
            _button("Topics", ACTION_ENGAGEMENT_TOPIC_LIST, "0"),
        ],
        [_button("Recent actions", ACTION_ENGAGEMENT_ACTIONS, "0")],
    ]
    if show_admin:
        rows.append([_button("Admin", ACTION_ENGAGEMENT_ADMIN)])
    return _inline_markup(_with_navigation(rows))


def engagement_admin_home_markup():
    rows = [
        [
            _button("Communities", ACTION_ENGAGEMENT_TARGETS, "0"),
            _button("Topics", ACTION_ENGAGEMENT_TOPIC_LIST, "0"),
        ],
        [
            _button("Voice rules", ACTION_ENGAGEMENT_STYLE, "0"),
            _button("Limits/accounts", ACTION_ENGAGEMENT_ADMIN_LIMITS),
        ],
        [_button("Advanced", ACTION_ENGAGEMENT_ADMIN_ADVANCED)],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_admin_limits_markup():
    rows = [[_button("Communities", ACTION_ENGAGEMENT_TARGETS, "0")]]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_ADMIN))


def engagement_admin_advanced_markup():
    rows = [
        [_button("Prompt profiles", ACTION_ENGAGEMENT_PROMPTS, "0")],
        [_button("Audit and diagnostics", ACTION_ENGAGEMENT_ACTIONS, "0")],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_ADMIN))


def engagement_target_list_markup(
    *,
    status: str | None,
    offset: int,
    total: int,
    page_size: int,
    can_manage: bool = True,
):
    rows = [*_target_status_filter_rows(status)]
    if can_manage:
        rows.insert(0, [_button("Add target", ACTION_ENGAGEMENT_TARGET_ADD)])
    pager_row = _offset_pager_row(
        action=ACTION_ENGAGEMENT_TARGETS,
        offset=offset,
        total=total,
        page_size=page_size,
        prefix_parts=[status or "all"],
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_ADMIN))


def engagement_target_actions_markup(
    target_id: str,
    *,
    status: str,
    allow_join: bool = False,
    allow_detect: bool = False,
    allow_post: bool = False,
    can_manage: bool = True,
):
    rows = []
    rows.append([_button("Open", ACTION_ENGAGEMENT_TARGET_OPEN, target_id)])
    if can_manage and status in {"pending", "failed"}:
        rows.append([_button("Resolve", ACTION_ENGAGEMENT_TARGET_RESOLVE, target_id)])
    if can_manage and status == "resolved":
        rows.append([_button("Approve", ACTION_ENGAGEMENT_TARGET_APPROVE, target_id)])
    if can_manage and status not in {"rejected", "archived"}:
        rows.append([_button("Edit notes", ACTION_ENGAGEMENT_TARGET_EDIT, target_id, "notes")])
        rows.append(
            [
                _button("Reject", ACTION_ENGAGEMENT_TARGET_REJECT, target_id),
                _button("Archive", ACTION_ENGAGEMENT_TARGET_ARCHIVE, target_id),
            ]
        )
    if can_manage and status == "approved":
        rows.extend(
            [
                [
                    _button(
                        "Watch off" if allow_detect else "Watch on",
                        ACTION_ENGAGEMENT_TARGET_PERMISSION,
                        target_id,
                        "d",
                        "0" if allow_detect else "1",
                    ),
                    _button(
                        "Post off" if allow_post else "Post on",
                        ACTION_ENGAGEMENT_TARGET_PERMISSION,
                        target_id,
                        "p",
                        "0" if allow_post else "1",
                    ),
                ],
                [
                    _button(
                        "Join off" if allow_join else "Join on",
                        ACTION_ENGAGEMENT_TARGET_PERMISSION,
                        target_id,
                        "j",
                        "0" if allow_join else "1",
                    )
                ],
                [
                    _button("Queue join", ACTION_ENGAGEMENT_TARGET_JOIN, target_id),
                    _button("Detect now", ACTION_ENGAGEMENT_TARGET_DETECT, target_id, "60"),
                ],
            ]
        )
    elif status == "approved":
        rows.append(
            [
                _button("Queue join", ACTION_ENGAGEMENT_TARGET_JOIN, target_id),
                _button("Detect now", ACTION_ENGAGEMENT_TARGET_DETECT, target_id, "60"),
            ]
        )
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_ENGAGEMENT_TARGETS, back_parts=["0"])
    )


def engagement_target_approval_confirm_markup(target_id: str):
    return _inline_markup(
        _with_navigation(
            [[_button("Confirm approval", ACTION_ENGAGEMENT_TARGET_APPROVE_CONFIRM, target_id)]],
            back_action=ACTION_ENGAGEMENT_TARGET_OPEN,
            back_parts=[target_id],
        )
    )


def engagement_target_permission_confirm_markup(
    target_id: str,
    *,
    permission_code: str,
    enabled: bool,
):
    return _inline_markup(
        _with_navigation(
            [
                [
                    _button(
                        "Confirm posting change",
                        ACTION_ENGAGEMENT_TARGET_PERMISSION_CONFIRM,
                        target_id,
                        permission_code,
                        "1" if enabled else "0",
                    )
                ]
            ],
            back_action=ACTION_ENGAGEMENT_TARGET_OPEN,
            back_parts=[target_id],
        )
    )


def engagement_prompt_actions_markup(profile_id: str, *, active: bool):
    rows = [
        [
            _button("Open", ACTION_ENGAGEMENT_PROMPT_OPEN, profile_id),
            _button("Preview", ACTION_ENGAGEMENT_PROMPT_PREVIEW, profile_id),
            _button("Versions", ACTION_ENGAGEMENT_PROMPT_VERSIONS, profile_id),
        ],
        [
            _button("Edit system", ACTION_ENGAGEMENT_PROMPT_EDIT, profile_id, "s"),
            _button("Edit user", ACTION_ENGAGEMENT_PROMPT_EDIT, profile_id, "u"),
        ],
        [
            _button("Edit model", ACTION_ENGAGEMENT_PROMPT_EDIT, profile_id, "m"),
            _button("Edit temp", ACTION_ENGAGEMENT_PROMPT_EDIT, profile_id, "t"),
            _button("Edit max", ACTION_ENGAGEMENT_PROMPT_EDIT, profile_id, "x"),
        ],
        [_button("Duplicate", ACTION_ENGAGEMENT_PROMPT_DUPLICATE, profile_id)],
    ]
    if not active:
        rows.append([_button("Activate", ACTION_ENGAGEMENT_PROMPT_ACTIVATE, profile_id)])
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_ENGAGEMENT_PROMPTS, back_parts=["0"])
    )


def engagement_prompt_list_markup(
    *,
    offset: int,
    total: int,
    page_size: int,
):
    rows = [[_button("Create profile", ACTION_ENGAGEMENT_PROMPT_CREATE)]]
    pager_row = _offset_pager_row(
        action=ACTION_ENGAGEMENT_PROMPTS,
        offset=offset,
        total=total,
        page_size=page_size,
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_ADMIN_ADVANCED))


def engagement_prompt_activation_confirm_markup(profile_id: str):
    return _inline_markup(
        _with_navigation(
            [[_button("Confirm activation", ACTION_ENGAGEMENT_PROMPT_ACTIVATE_CONFIRM, profile_id)]],
            back_action=ACTION_ENGAGEMENT_PROMPT_OPEN,
            back_parts=[profile_id],
        )
    )


def engagement_prompt_versions_markup(profile_id: str, versions: Sequence[dict[str, object]]):
    rows = []
    for version in versions[:5]:
        version_number = version.get("version_number")
        if version_number is None:
            continue
        rows.append(
            [
                _button(
                    f"Rollback v{version_number}",
                    ACTION_ENGAGEMENT_PROMPT_ROLLBACK,
                    profile_id,
                    str(version_number),
                )
            ]
        )
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_ENGAGEMENT_PROMPT_OPEN, back_parts=[profile_id])
    )


def engagement_prompt_rollback_confirm_markup(profile_id: str, version_number: int):
    return _inline_markup(
        _with_navigation(
            [
                [
                    _button(
                        f"Confirm rollback to v{version_number}",
                        ACTION_ENGAGEMENT_PROMPT_ROLLBACK_CONFIRM,
                        profile_id,
                        str(version_number),
                    )
                ]
            ],
            back_action=ACTION_ENGAGEMENT_PROMPT_VERSIONS,
            back_parts=[profile_id],
        )
    )


def engagement_admin_pager_markup(
    *,
    action: str,
    offset: int,
    total: int,
    page_size: int,
):
    rows = []
    pager_row = _offset_pager_row(action=action, offset=offset, total=total, page_size=page_size)
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_ADMIN))


def engagement_style_list_markup(
    *,
    scope_type: str | None,
    scope_id: str | None,
    offset: int,
    total: int,
    page_size: int,
    can_manage: bool = True,
):
    selected = scope_type or "all"
    scope_token = scope_type or "all"
    scope_id_token = scope_id or "-"
    rows = [
        [
            _button("* All" if selected == "all" else "All", ACTION_ENGAGEMENT_STYLE, "all", "-", "0"),
            _button(
                "* Global" if selected == "global" else "Global",
                ACTION_ENGAGEMENT_STYLE,
                "global",
                "-",
                "0",
            ),
        ],
        [
            _button(
                "* Account" if selected == "account" else "Account",
                ACTION_ENGAGEMENT_STYLE,
                "account",
                scope_id_token if selected == "account" else "-",
                "0",
            ),
            _button(
                "* Community" if selected == "community" else "Community",
                ACTION_ENGAGEMENT_STYLE,
                "community",
                scope_id_token if selected == "community" else "-",
                "0",
            ),
        ],
        [
            _button(
                "* Topic" if selected == "topic" else "Topic",
                ACTION_ENGAGEMENT_STYLE,
                "topic",
                scope_id_token if selected == "topic" else "-",
                "0",
            )
        ],
    ]
    if can_manage:
        rows.insert(0, [_button("Create", ACTION_ENGAGEMENT_STYLE_CREATE)])
    pager_row = _offset_pager_row(
        action=ACTION_ENGAGEMENT_STYLE,
        offset=offset,
        total=total,
        page_size=page_size,
        prefix_parts=[scope_token, scope_id_token],
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_ADMIN))


def engagement_style_rule_actions_markup(rule_id: str, *, active: bool, can_manage: bool = True):
    rows = [[_button("Open", ACTION_ENGAGEMENT_STYLE_OPEN, rule_id)]]
    if can_manage:
        rows.extend(
            [
                [_button("Edit", ACTION_ENGAGEMENT_STYLE_EDIT, rule_id)],
                [
                    _button(
                        "Disable" if active else "Enable",
                        ACTION_ENGAGEMENT_STYLE_TOGGLE,
                        rule_id,
                        "0" if active else "1",
                    )
                ],
            ]
        )
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_STYLE, back_parts=["all", "-", "0"]))


def engagement_settings_markup(
    community_id: str,
    *,
    allow_join: bool,
    allow_post: bool,
    can_manage: bool = True,
):
    rows = []
    if can_manage:
        rows.extend(
            [
                [
                    _button("Off", ACTION_ENGAGEMENT_SETTINGS_PRESET, community_id, "off"),
                    _button("Observe", ACTION_ENGAGEMENT_SETTINGS_PRESET, community_id, "observe"),
                ],
                [
                    _button("Suggest", ACTION_ENGAGEMENT_SETTINGS_PRESET, community_id, "suggest"),
                    _button("Ready", ACTION_ENGAGEMENT_SETTINGS_PRESET, community_id, "ready"),
                ],
                [
                    _button(
                        "Join on" if not allow_join else "Join off",
                        ACTION_ENGAGEMENT_SETTINGS_JOIN,
                        community_id,
                        "1" if not allow_join else "0",
                    ),
                    _button(
                        "Post on" if not allow_post else "Post off",
                        ACTION_ENGAGEMENT_SETTINGS_POST,
                        community_id,
                        "1" if not allow_post else "0",
                    ),
                ],
                [
                    _button(
                        "Edit max/day",
                        ACTION_ENGAGEMENT_SETTINGS_EDIT,
                        community_id,
                        "mp",
                    ),
                    _button(
                        "Edit gap",
                        ACTION_ENGAGEMENT_SETTINGS_EDIT,
                        community_id,
                        "gap",
                    ),
                ],
                [
                    _button(
                        "Quiet start",
                        ACTION_ENGAGEMENT_SETTINGS_EDIT,
                        community_id,
                        "qs",
                    ),
                    _button(
                        "Quiet end",
                        ACTION_ENGAGEMENT_SETTINGS_EDIT,
                        community_id,
                        "qe",
                    ),
                ],
                [
                    _button(
                        "Assign account",
                        ACTION_ENGAGEMENT_SETTINGS_EDIT,
                        community_id,
                        "acct",
                    )
                ],
            ]
        )
    rows.append(
        [
            _button("Queue join", ACTION_ENGAGEMENT_JOIN, community_id),
            _button("Detect now", ACTION_ENGAGEMENT_DETECT, community_id, "60"),
        ]
    )
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_OPEN_COMMUNITY, back_parts=[community_id])
    )


def engagement_account_confirm_markup():
    return _inline_markup(
        [
            [
                _button("Confirm account change", ACTION_ENGAGEMENT_ACCOUNT_CONFIRM),
                _button("Cancel", ACTION_ENGAGEMENT_ACCOUNT_CANCEL),
            ]
        ]
    )


def engagement_topic_pager_markup(
    *,
    offset: int,
    total: int,
    page_size: int,
):
    rows = []
    pager_row = _offset_pager_row(
        action=ACTION_ENGAGEMENT_TOPIC_LIST,
        offset=offset,
        total=total,
        page_size=page_size,
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_topic_actions_markup(
    topic_id: str,
    *,
    active: bool,
    good_count: int = 0,
    bad_count: int = 0,
    can_manage: bool = True,
):
    rows = [[_button("Open", ACTION_ENGAGEMENT_TOPIC_OPEN, topic_id)]]
    if can_manage:
        rows.extend(
            [
                [
                    _button("Edit guidance", ACTION_ENGAGEMENT_TOPIC_EDIT, topic_id, "stance_guidance"),
                    _button("Edit triggers", ACTION_ENGAGEMENT_TOPIC_EDIT, topic_id, "trigger_keywords"),
                ],
                [
                    _button("Edit negatives", ACTION_ENGAGEMENT_TOPIC_EDIT, topic_id, "negative_keywords"),
                    _button(
                        "Deactivate" if active else "Activate",
                        ACTION_ENGAGEMENT_TOPIC_TOGGLE,
                        topic_id,
                        "0" if active else "1",
                    ),
                ],
                [
                    _button("Add good example", ACTION_ENGAGEMENT_TOPIC_EXAMPLE_ADD, topic_id, "g"),
                    _button("Add bad example", ACTION_ENGAGEMENT_TOPIC_EXAMPLE_ADD, topic_id, "b"),
                ],
            ]
        )
    if can_manage and (good_count > 0 or bad_count > 0):
        remove_row = []
        if good_count > 0:
            remove_row.append(
                _button(
                    "Remove good #1",
                    ACTION_ENGAGEMENT_TOPIC_EXAMPLE_REMOVE,
                    topic_id,
                    "g",
                    "0",
                )
            )
        if bad_count > 0:
            remove_row.append(
                _button(
                    "Remove bad #1",
                    ACTION_ENGAGEMENT_TOPIC_EXAMPLE_REMOVE,
                    topic_id,
                    "b",
                    "0",
                )
            )
        rows.append(remove_row)
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_ENGAGEMENT_TOPIC_LIST, back_parts=["0"])
    )


def engagement_candidate_filter_markup(*, status: str = "needs_review"):
    statuses = ["needs_review", "approved", "failed", "sent", "rejected"]
    rows = []
    row = []
    for candidate_status in statuses:
        label = candidate_status.replace("_", " ")
        if candidate_status == status:
            label = f"* {label}"
        row.append(_button(label.title(), ACTION_ENGAGEMENT_CANDIDATES, candidate_status, "0"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_action_pager_markup(
    *,
    offset: int,
    total: int,
    page_size: int,
    community_id: str | None = None,
):
    rows = []
    prefix_parts = [community_id] if community_id else []
    pager_row = _offset_pager_row(
        action=ACTION_ENGAGEMENT_ACTIONS,
        offset=offset,
        total=total,
        page_size=page_size,
        prefix_parts=prefix_parts,
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_job_markup(
    job_id: str,
    *,
    community_id: str | None = None,
    candidate_id: str | None = None,
):
    rows = [[_button("Refresh Job", ACTION_JOB_STATUS, job_id)]]
    if community_id:
        rows.append([_button("Community", ACTION_OPEN_COMMUNITY, community_id)])
    if candidate_id:
        rows.append([_button("Reply", ACTION_ENGAGEMENT_CANDIDATE_OPEN, candidate_id)])
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_ENGAGEMENT_ACTIONS, back_parts=["0"])
    )


def config_edit_confirmation_markup():
    return _inline_markup(
        [
            [
                _button("Save", ACTION_CONFIG_EDIT_SAVE),
                _button("Cancel", ACTION_CONFIG_EDIT_CANCEL),
            ]
        ]
    )


def review_result_markup(community_id: str, job_id: str | None = None):
    rows = [[_button("Community", ACTION_OPEN_COMMUNITY, community_id)]]
    if job_id:
        rows.append([_button("Snapshot Job", ACTION_JOB_STATUS, job_id)])
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_OPEN_COMMUNITY, back_parts=[community_id])
    )


def community_actions_markup(community_id: str):
    rows = [
        [_button("Snapshot", ACTION_SNAPSHOT_COMMUNITY, community_id)],
        [
            _button("Members", ACTION_COMMUNITY_MEMBERS, community_id, "0"),
            _button("Engagement", ACTION_ENGAGEMENT_SETTINGS_OPEN, community_id),
        ],
        [_button("Refresh", ACTION_OPEN_COMMUNITY, community_id)],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_HOME))


def member_pager_markup(
    community_id: str,
    *,
    offset: int,
    total: int,
    page_size: int,
):
    rows = []
    pager_row = _pager_row(
        action=ACTION_COMMUNITY_MEMBERS,
        item_id=community_id,
        offset=offset,
        total=total,
        page_size=page_size,
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_OPEN_COMMUNITY, back_parts=[community_id])
    )


def job_actions_markup(job_id: str):
    rows = [[_button("Refresh Job", ACTION_JOB_STATUS, job_id)]]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_ACTIVITY))


def parse_callback_data(data: str) -> tuple[str, list[str]]:
    parts = data.split(":")
    if parts[0] == "eng":
        if len(parts) >= 3 and parts[1] == "admin":
            return ":".join(parts[:3]), parts[3:]
        if len(parts) >= 3 and parts[1] in {"actions", "cand", "edit", "set", "topic"}:
            return ":".join(parts[:3]), parts[3:]
        if len(parts) >= 2:
            return ":".join(parts[:2]), parts[2:]
    if parts[0] in {"op", "disc"} and len(parts) >= 2:
        return ":".join(parts[:2]), parts[2:]
    return parts[0], parts[1:]


def encode_callback_data(action: str, *parts: str) -> str:
    data = ":".join([action, *parts])
    if len(data) > 64:
        raise ValueError(f"Callback data too long for Telegram: {data}")
    return data


def _button(label: str, action: str, *parts: str):
    InlineKeyboardButton, _ = _inline_types()

    return InlineKeyboardButton(label, callback_data=encode_callback_data(action, *parts))


def _inline_markup(rows: Sequence[Sequence[object]]):
    _, InlineKeyboardMarkup = _inline_types()

    return InlineKeyboardMarkup(rows)


def _with_navigation(
    rows: Sequence[Sequence[object]],
    *,
    back_action: str | None = None,
    back_parts: Sequence[str] = (),
    include_home: bool = True,
) -> list[list[object]]:
    output = [list(row) for row in rows]
    nav_row = []
    if back_action is not None:
        nav_row.append(_button("Back", back_action, *back_parts))
    if include_home:
        nav_row.append(_button("Home", ACTION_OP_HOME))
    if nav_row:
        output.append(nav_row)
    return output


def _pager_row(
    *,
    action: str,
    item_id: str,
    offset: int,
    total: int,
    page_size: int,
):
    buttons = []
    previous_offset = max(offset - page_size, 0)
    next_offset = offset + page_size
    if offset > 0:
        buttons.append(_button("Prev", action, item_id, str(previous_offset)))
    if next_offset < total:
        buttons.append(_button("Next", action, item_id, str(next_offset)))
    return buttons


def _offset_pager_row(
    *,
    action: str,
    offset: int,
    total: int,
    page_size: int,
    prefix_parts: Sequence[str] = (),
):
    buttons = []
    previous_offset = max(offset - page_size, 0)
    next_offset = offset + page_size
    if offset > 0:
        buttons.append(_button("Prev", action, *prefix_parts, str(previous_offset)))
    if next_offset < total:
        buttons.append(_button("Next", action, *prefix_parts, str(next_offset)))
    return buttons


def _target_status_filter_rows(status: str | None):
    labels = [
        ("all", "All"),
        ("pending", "Pending"),
        ("resolved", "Resolved"),
        ("approved", "Approved"),
        ("failed", "Failed"),
        ("rejected", "Rejected"),
        ("archived", "Archived"),
    ]
    rows = []
    row = []
    selected = status or "all"
    for value, label in labels:
        display_label = f"* {label}" if value == selected else label
        row.append(_button(display_label, ACTION_ENGAGEMENT_TARGETS, value, "0"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def _inline_types():
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        return _FallbackInlineKeyboardButton, _FallbackInlineKeyboardMarkup
    return InlineKeyboardButton, InlineKeyboardMarkup


def _keyboard_types():
    try:
        from telegram import KeyboardButton, ReplyKeyboardMarkup
    except ImportError:
        return _FallbackKeyboardButton, _FallbackReplyKeyboardMarkup
    return KeyboardButton, ReplyKeyboardMarkup
