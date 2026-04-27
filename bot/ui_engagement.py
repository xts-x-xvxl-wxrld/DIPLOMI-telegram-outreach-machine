from __future__ import annotations

from typing import Sequence

from .ui_common import (
    ACTION_OPEN_COMMUNITY,
    ACTION_JOB_STATUS,
    ACTION_ENGAGEMENT_HOME,
    ACTION_ENGAGEMENT_CANDIDATES,
    ACTION_ENGAGEMENT_APPROVE,
    ACTION_ENGAGEMENT_REJECT,
    ACTION_ENGAGEMENT_SEND,
    ACTION_ENGAGEMENT_CANDIDATE_OPEN,
    ACTION_ENGAGEMENT_CANDIDATE_EDIT,
    ACTION_ENGAGEMENT_CANDIDATE_REVISIONS,
    ACTION_ENGAGEMENT_CANDIDATE_EXPIRE,
    ACTION_ENGAGEMENT_CANDIDATE_RETRY,
    ACTION_ENGAGEMENT_TOPIC_LIST,
    ACTION_ENGAGEMENT_TOPIC_CREATE,
    ACTION_ENGAGEMENT_SETTINGS_OPEN,
    ACTION_ENGAGEMENT_SETTINGS_LOOKUP,
    ACTION_ENGAGEMENT_SETTINGS_PRESET,
    ACTION_ENGAGEMENT_SETTINGS_JOIN,
    ACTION_ENGAGEMENT_SETTINGS_POST,
    ACTION_ENGAGEMENT_SETTINGS_EDIT,
    ACTION_ENGAGEMENT_ACCOUNT_CONFIRM,
    ACTION_ENGAGEMENT_ACCOUNT_CANCEL,
    ACTION_ENGAGEMENT_JOIN,
    ACTION_ENGAGEMENT_DETECT,
    ACTION_ENGAGEMENT_ACTIONS,
    ACTION_ENGAGEMENT_ADMIN,
    ACTION_ENGAGEMENT_TARGETS,
    ACTION_ENGAGEMENT_TARGET_ADD,
    ACTION_ENGAGEMENT_TARGET_OPEN,
    ACTION_ENGAGEMENT_TARGET_APPROVE,
    ACTION_ENGAGEMENT_TARGET_APPROVE_CONFIRM,
    ACTION_ENGAGEMENT_TARGET_RESOLVE,
    ACTION_ENGAGEMENT_TARGET_REJECT,
    ACTION_ENGAGEMENT_TARGET_ARCHIVE,
    ACTION_ENGAGEMENT_TARGET_PERMISSION,
    ACTION_ENGAGEMENT_TARGET_PERMISSION_CONFIRM,
    ACTION_ENGAGEMENT_TARGET_EDIT,
    ACTION_ENGAGEMENT_TARGET_JOIN,
    ACTION_ENGAGEMENT_TARGET_DETECT,
    ACTION_ENGAGEMENT_PROMPTS,
    ACTION_ENGAGEMENT_PROMPT_OPEN,
    ACTION_ENGAGEMENT_PROMPT_PREVIEW,
    ACTION_ENGAGEMENT_PROMPT_VERSIONS,
    ACTION_ENGAGEMENT_PROMPT_EDIT,
    ACTION_ENGAGEMENT_PROMPT_CREATE,
    ACTION_ENGAGEMENT_PROMPT_DUPLICATE,
    ACTION_ENGAGEMENT_PROMPT_ACTIVATE,
    ACTION_ENGAGEMENT_PROMPT_ACTIVATE_CONFIRM,
    ACTION_ENGAGEMENT_PROMPT_ROLLBACK,
    ACTION_ENGAGEMENT_PROMPT_ROLLBACK_CONFIRM,
    ACTION_ENGAGEMENT_STYLE,
    ACTION_ENGAGEMENT_STYLE_CREATE,
    ACTION_ENGAGEMENT_STYLE_OPEN,
    ACTION_ENGAGEMENT_STYLE_EDIT,
    ACTION_ENGAGEMENT_STYLE_TOGGLE,
    ACTION_ENGAGEMENT_ADMIN_LIMITS,
    ACTION_ENGAGEMENT_ADMIN_ADVANCED,
    ACTION_CONFIG_EDIT_SAVE,
    ACTION_CONFIG_EDIT_CANCEL,
    _button,
    _inline_markup,
    _with_navigation,
    _offset_pager_row,
    _compact_label,
    _target_status_filter_rows,
)

def engagement_candidate_actions_markup(candidate_id: str):
    rows = [
        [_button("👀 Open", ACTION_ENGAGEMENT_CANDIDATE_OPEN, candidate_id)],
        [
            _button("✏ Edit", ACTION_ENGAGEMENT_CANDIDATE_EDIT, candidate_id),
            _button("✅ Approve", ACTION_ENGAGEMENT_APPROVE, candidate_id),
            _button("✖ Reject", ACTION_ENGAGEMENT_REJECT, candidate_id),
        ],
        [_button("⚠ Pending approvals", ACTION_ENGAGEMENT_CANDIDATES, "needs_review", "0")],
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
        [_button("📤 Queue send", ACTION_ENGAGEMENT_SEND, candidate_id)],
        [_button("👀 Open", ACTION_ENGAGEMENT_CANDIDATE_OPEN, candidate_id)],
        [_button("✅ Ready to send", ACTION_ENGAGEMENT_CANDIDATES, "approved", "0")],
    ]
    return _inline_markup(
        _with_navigation(
            rows,
            back_action=ACTION_ENGAGEMENT_CANDIDATES,
            back_parts=["approved", "0"],
        )
    )


def engagement_candidate_detail_markup(
    candidate_id: str,
    *,
    status: str,
    community_id: str | None = None,
    blocked: bool = False,
):
    has_fix_row = bool(community_id and (blocked or status == "failed"))
    rows = [[_button("🗂 Revisions", ACTION_ENGAGEMENT_CANDIDATE_REVISIONS, candidate_id)]]
    if has_fix_row:
        rows.insert(
            0,
            [
                _button("⚙ Fix settings", ACTION_ENGAGEMENT_SETTINGS_OPEN, str(community_id)),
                _button("📜 Recent actions", ACTION_ENGAGEMENT_ACTIONS, str(community_id), "0"),
            ],
        )
    if status == "needs_review":
        rows.insert(
            1 if has_fix_row else 0,
            [
                _button("✏ Edit", ACTION_ENGAGEMENT_CANDIDATE_EDIT, candidate_id),
                _button("✅ Approve", ACTION_ENGAGEMENT_APPROVE, candidate_id),
                _button("✖ Reject", ACTION_ENGAGEMENT_REJECT, candidate_id),
            ],
        )
        rows.append([_button("⏳ Expire", ACTION_ENGAGEMENT_CANDIDATE_EXPIRE, candidate_id)])
    elif status == "approved":
        rows.insert(
            1 if has_fix_row else 0,
            [_button("📤 Queue send", ACTION_ENGAGEMENT_SEND, candidate_id)],
        )
        rows.insert(
            2 if has_fix_row else 1,
            [
                _button("✏ Edit", ACTION_ENGAGEMENT_CANDIDATE_EDIT, candidate_id),
                _button("✖ Reject", ACTION_ENGAGEMENT_REJECT, candidate_id),
            ],
        )
        rows.append([_button("⏳ Expire", ACTION_ENGAGEMENT_CANDIDATE_EXPIRE, candidate_id)])
    elif status == "failed":
        rows.insert(
            1 if has_fix_row else 0,
            [
                _button("🔁 Retry", ACTION_ENGAGEMENT_CANDIDATE_RETRY, candidate_id),
                _button("✏ Edit", ACTION_ENGAGEMENT_CANDIDATE_EDIT, candidate_id),
                _button("✖ Reject", ACTION_ENGAGEMENT_REJECT, candidate_id),
            ],
        )
        rows.append([_button("⏳ Expire", ACTION_ENGAGEMENT_CANDIDATE_EXPIRE, candidate_id)])
    return _inline_markup(
        _with_navigation(
            rows,
            back_action=ACTION_ENGAGEMENT_CANDIDATES,
            back_parts=[
                status if status in {"approved", "failed", "sent", "rejected", "expired"} else "needs_review",
                "0",
            ],
        )
    )


def engagement_candidate_revisions_markup(candidate_id: str):
    rows = [[_button("👀 Open", ACTION_ENGAGEMENT_CANDIDATE_OPEN, candidate_id)]]
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
        [_button("⚠ Pending approvals", ACTION_ENGAGEMENT_CANDIDATES, "needs_review", "0")],
        [
            _button("✅ Ready to send", ACTION_ENGAGEMENT_CANDIDATES, "approved", "0"),
            _button("⛔ Needs attention", ACTION_ENGAGEMENT_CANDIDATES, "failed", "0"),
        ],
        [
            _button("🏘 Communities", ACTION_ENGAGEMENT_TARGETS, "0"),
            _button("🧩 Topics", ACTION_ENGAGEMENT_TOPIC_LIST, "0"),
        ],
        [
            _button("⚙ Settings", ACTION_ENGAGEMENT_SETTINGS_LOOKUP, "0"),
            _button("📜 Actions", ACTION_ENGAGEMENT_ACTIONS, "0"),
        ],
    ]
    if show_admin:
        rows.append([_button("🛠 Admin", ACTION_ENGAGEMENT_ADMIN)])
    return _inline_markup(_with_navigation(rows))


def engagement_admin_home_markup():
    rows = [
        [
            _button("🏘 Communities", ACTION_ENGAGEMENT_TARGETS, "0"),
            _button("🧩 Topics", ACTION_ENGAGEMENT_TOPIC_LIST, "0"),
        ],
        [
            _button("➕ Add community", ACTION_ENGAGEMENT_TARGET_ADD),
            _button("➕ Create topic", ACTION_ENGAGEMENT_TOPIC_CREATE),
        ],
        [
            _button("🗣 Reply style", ACTION_ENGAGEMENT_STYLE, "0"),
            _button("⚙ Send safety", ACTION_ENGAGEMENT_ADMIN_LIMITS),
        ],
        [_button("🧠 Drafting/audit", ACTION_ENGAGEMENT_ADMIN_ADVANCED)],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_admin_limits_markup():
    rows = [
        [_button("⚙ Safety lookup", ACTION_ENGAGEMENT_SETTINGS_LOOKUP, "0")],
        [_button("🏘 Communities", ACTION_ENGAGEMENT_TARGETS, "0")],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_ADMIN))


def engagement_settings_lookup_markup(
    items: Sequence[dict[str, object]],
    *,
    offset: int,
    total: int,
    page_size: int,
):
    rows = []
    for item in items:
        community_id = item.get("community_id")
        if not community_id:
            continue
        label = str(item.get("community_title") or item.get("submitted_ref") or community_id)
        rows.append(
            [
                _button(
                    f"⚙ {_compact_label(label, 38)}",
                    ACTION_ENGAGEMENT_SETTINGS_OPEN,
                    str(community_id),
                )
            ]
        )
    pager_row = _offset_pager_row(
        action=ACTION_ENGAGEMENT_SETTINGS_LOOKUP,
        offset=offset,
        total=total,
        page_size=page_size,
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_HOME))


def engagement_admin_advanced_markup():
    rows = [
        [_button("🧠 Drafting profiles", ACTION_ENGAGEMENT_PROMPTS, "0")],
        [_button("📜 Audit/diagnostics", ACTION_ENGAGEMENT_ACTIONS, "0")],
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
        rows.insert(0, [_button("➕ Add target", ACTION_ENGAGEMENT_TARGET_ADD)])
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
    community_id: str | None = None,
    allow_join: bool = False,
    allow_detect: bool = False,
    allow_post: bool = False,
    can_manage: bool = True,
):
    rows = []
    rows.append([_button("👀 Open", ACTION_ENGAGEMENT_TARGET_OPEN, target_id)])
    if community_id:
        rows.append([_button("⚙ Settings", ACTION_ENGAGEMENT_SETTINGS_OPEN, community_id)])
    if can_manage and status in {"pending", "failed"}:
        rows.append([_button("🪄 Resolve", ACTION_ENGAGEMENT_TARGET_RESOLVE, target_id)])
    if can_manage and status == "resolved":
        rows.append([_button("✅ Approve", ACTION_ENGAGEMENT_TARGET_APPROVE, target_id)])
    if can_manage and status not in {"rejected", "archived"}:
        rows.append([_button("✏ Edit notes", ACTION_ENGAGEMENT_TARGET_EDIT, target_id, "notes")])
        rows.append(
            [
                _button("✖ Reject", ACTION_ENGAGEMENT_TARGET_REJECT, target_id),
                _button("🗄 Archive", ACTION_ENGAGEMENT_TARGET_ARCHIVE, target_id),
            ]
        )
    if can_manage and status == "approved":
        rows.extend(
            [
                [
                    _button(
                        "👀 Watch off" if allow_detect else "👀 Watch on",
                        ACTION_ENGAGEMENT_TARGET_PERMISSION,
                        target_id,
                        "d",
                        "0" if allow_detect else "1",
                    ),
                    _button(
                        "📣 Post off" if allow_post else "📣 Post on",
                        ACTION_ENGAGEMENT_TARGET_PERMISSION,
                        target_id,
                        "p",
                        "0" if allow_post else "1",
                    ),
                ],
                [
                    _button(
                        "🤝 Join off" if allow_join else "🤝 Join on",
                        ACTION_ENGAGEMENT_TARGET_PERMISSION,
                        target_id,
                        "j",
                        "0" if allow_join else "1",
                    )
                ],
                [
                    _button("🤝 Queue join", ACTION_ENGAGEMENT_TARGET_JOIN, target_id),
                    _button("🔎 Detect now", ACTION_ENGAGEMENT_TARGET_DETECT, target_id, "60"),
                ],
            ]
        )
    elif status == "approved":
        rows.append(
            [
                _button("🤝 Queue join", ACTION_ENGAGEMENT_TARGET_JOIN, target_id),
                _button("🔎 Detect now", ACTION_ENGAGEMENT_TARGET_DETECT, target_id, "60"),
            ]
        )
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_ENGAGEMENT_TARGETS, back_parts=["0"])
    )


def engagement_target_approval_confirm_markup(target_id: str):
    return _inline_markup(
        _with_navigation(
            [[_button("✅ Confirm approval", ACTION_ENGAGEMENT_TARGET_APPROVE_CONFIRM, target_id)]],
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
                        "✅ Confirm change",
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
            _button("👀 Open", ACTION_ENGAGEMENT_PROMPT_OPEN, profile_id),
            _button("🔍 Preview", ACTION_ENGAGEMENT_PROMPT_PREVIEW, profile_id),
            _button("🗂 Versions", ACTION_ENGAGEMENT_PROMPT_VERSIONS, profile_id),
        ],
        [
            _button("✏ System", ACTION_ENGAGEMENT_PROMPT_EDIT, profile_id, "s"),
            _button("✏ User", ACTION_ENGAGEMENT_PROMPT_EDIT, profile_id, "u"),
        ],
        [
            _button("🤖 Model", ACTION_ENGAGEMENT_PROMPT_EDIT, profile_id, "m"),
            _button("🌡 Temp", ACTION_ENGAGEMENT_PROMPT_EDIT, profile_id, "t"),
            _button("📏 Max", ACTION_ENGAGEMENT_PROMPT_EDIT, profile_id, "x"),
        ],
        [_button("🪞 Duplicate", ACTION_ENGAGEMENT_PROMPT_DUPLICATE, profile_id)],
    ]
    if not active:
        rows.append([_button("✅ Activate", ACTION_ENGAGEMENT_PROMPT_ACTIVATE, profile_id)])
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_ENGAGEMENT_PROMPTS, back_parts=["0"])
    )


def engagement_prompt_list_markup(
    *,
    offset: int,
    total: int,
    page_size: int,
):
    rows = [[_button("➕ Create profile", ACTION_ENGAGEMENT_PROMPT_CREATE)]]
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
            [[_button("✅ Confirm activation", ACTION_ENGAGEMENT_PROMPT_ACTIVATE_CONFIRM, profile_id)]],
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
                    _button("⏸ Off", ACTION_ENGAGEMENT_SETTINGS_PRESET, community_id, "off"),
                    _button("👀 Observe", ACTION_ENGAGEMENT_SETTINGS_PRESET, community_id, "observe"),
                ],
                [
                    _button("✍ Suggest", ACTION_ENGAGEMENT_SETTINGS_PRESET, community_id, "suggest"),
                    _button("✅ Ready", ACTION_ENGAGEMENT_SETTINGS_PRESET, community_id, "ready"),
                ],
                [
                    _button(
                        "🤝 Join on" if not allow_join else "🤝 Join off",
                        ACTION_ENGAGEMENT_SETTINGS_JOIN,
                        community_id,
                        "1" if not allow_join else "0",
                    ),
                    _button(
                        "📣 Post on" if not allow_post else "📣 Post off",
                        ACTION_ENGAGEMENT_SETTINGS_POST,
                        community_id,
                        "1" if not allow_post else "0",
                    ),
                ],
                [
                    _button(
                        "📏 Max/day",
                        ACTION_ENGAGEMENT_SETTINGS_EDIT,
                        community_id,
                        "mp",
                    ),
                    _button(
                        "⏱ Edit gap",
                        ACTION_ENGAGEMENT_SETTINGS_EDIT,
                        community_id,
                        "gap",
                    ),
                ],
                [
                    _button(
                        "🌙 Quiet start",
                        ACTION_ENGAGEMENT_SETTINGS_EDIT,
                        community_id,
                        "qs",
                    ),
                    _button(
                        "🌅 Quiet end",
                        ACTION_ENGAGEMENT_SETTINGS_EDIT,
                        community_id,
                        "qe",
                    ),
                ],
                [
                    _button(
                        "📲 Assign account",
                        ACTION_ENGAGEMENT_SETTINGS_EDIT,
                        community_id,
                        "acct",
                    )
                ],
            ]
        )
    rows.append(
        [
            _button("🤝 Queue join", ACTION_ENGAGEMENT_JOIN, community_id),
            _button("🔎 Detect now", ACTION_ENGAGEMENT_DETECT, community_id, "60"),
        ]
    )
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_OPEN_COMMUNITY, back_parts=[community_id])
    )


def engagement_account_confirm_markup():
    return _inline_markup(
        [
            [
                _button("✅ Confirm account", ACTION_ENGAGEMENT_ACCOUNT_CONFIRM),
                _button("✖ Cancel", ACTION_ENGAGEMENT_ACCOUNT_CANCEL),
            ]
        ]
    )

def engagement_candidate_filter_markup(*, status: str = "needs_review"):
    labels = {
        "needs_review": "Pending approvals",
        "approved": "Ready to send",
        "failed": "Needs attention",
        "expired": "Expired",
        "sent": "Sent",
        "rejected": "Rejected",
    }
    statuses = ["needs_review", "approved", "failed", "expired", "sent", "rejected"]
    rows = []
    row = []
    for candidate_status in statuses:
        label = labels.get(candidate_status, candidate_status.replace("_", " ").title())
        if candidate_status == status:
            label = f"• {label}"
        row.append(_button(label, ACTION_ENGAGEMENT_CANDIDATES, candidate_status, "0"))
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
    rows = []
    try:
        rows.append([_button("Refresh Job", ACTION_JOB_STATUS, job_id)])
    except ValueError:
        rows = []
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
