from __future__ import annotations

from .ui_common import (
    ACTION_OP_DISCOVERY,
    ACTION_OP_ACCOUNTS,
    ACTION_OP_ACCOUNT_HEALTH,
    ACTION_OP_ADD_ACCOUNT,
    ACTION_OP_ACCOUNT_SKIP,
    ACTION_OP_HELP,
    ACTION_DISC_HOME,
    ACTION_DISC_START,
    ACTION_DISC_ATTENTION,
    ACTION_DISC_REVIEW,
    ACTION_DISC_WATCHING,
    ACTION_DISC_ACTIVITY,
    ACTION_DISC_HELP,
    ACTION_DISC_ALL,
    ACTION_OPEN_SEED_GROUP,
    ACTION_RESOLVE_SEED_GROUP,
    ACTION_SEED_CHANNELS,
    ACTION_SEED_CANDIDATES,
    ACTION_OPEN_COMMUNITY,
    ACTION_APPROVE_COMMUNITY,
    ACTION_REJECT_COMMUNITY,
    ACTION_SNAPSHOT_COMMUNITY,
    ACTION_COMMUNITY_MEMBERS,
    ACTION_JOB_STATUS,
    ACTION_ENGAGEMENT_HOME,
    ACTION_ENGAGEMENT_SETTINGS_OPEN,
    _button,
    _inline_markup,
    _with_navigation,
    _pager_row,
    _FallbackReplyKeyboardRemove,
)

def operator_cockpit_markup():
    return _inline_markup(
        [
            [_button("🔎 Discovery", ACTION_OP_DISCOVERY)],
            [_button("💬 Engagement", ACTION_ENGAGEMENT_HOME)],
            [_button("📲 Accounts", ACTION_OP_ACCOUNTS)],
            [_button("❓ Help", ACTION_OP_HELP)],
        ]
    )


def discovery_cockpit_markup():
    rows = [
        [_button("➕ Start search", ACTION_DISC_START)],
        [_button("⚠ Needs attention", ACTION_DISC_ATTENTION)],
        [_button("🧩 Review communities", ACTION_DISC_REVIEW)],
        [_button("👀 Watching", ACTION_DISC_WATCHING)],
        [_button("🕒 Recent activity", ACTION_DISC_ACTIVITY)],
        [_button("❓ Help", ACTION_DISC_HELP)],
    ]
    return _inline_markup(_with_navigation(rows))


def discovery_seeds_markup():
    return _inline_markup(_with_navigation([], back_action=ACTION_DISC_HOME))


def accounts_cockpit_markup():
    rows = [
        [_button("Run health check", ACTION_OP_ACCOUNT_HEALTH)],
        [
            _button("Add search", ACTION_OP_ADD_ACCOUNT, "search"),
            _button("Add engagement", ACTION_OP_ADD_ACCOUNT, "engagement"),
        ],
        [_button("Refresh", ACTION_OP_ACCOUNTS)],
    ]
    return _inline_markup(_with_navigation(rows))


def account_onboarding_prompt_markup(*, allow_skip: bool = False):
    rows = [[_button("Skip", ACTION_OP_ACCOUNT_SKIP)]] if allow_skip else []
    return _inline_markup(rows) if rows else None


def reply_keyboard_remove():
    try:
        from telegram import ReplyKeyboardRemove
    except ImportError:
        return _FallbackReplyKeyboardRemove()
    return ReplyKeyboardRemove()


def seed_group_actions_markup(seed_group_id: str):
    rows = [
        [_button("👀 Open", ACTION_OPEN_SEED_GROUP, seed_group_id)],
        [
            _button("🪄 Resolve", ACTION_RESOLVE_SEED_GROUP, seed_group_id),
            _button("📡 Channels", ACTION_SEED_CHANNELS, seed_group_id, "0"),
        ],
        [_button("🧩 Candidates", ACTION_SEED_CANDIDATES, seed_group_id, "0")],
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
    rows = [[_button("🌱 Seed Group", ACTION_OPEN_SEED_GROUP, seed_group_id)]]
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
            _button("✅ Approve", ACTION_APPROVE_COMMUNITY, community_id),
            _button("✖ Reject", ACTION_REJECT_COMMUNITY, community_id),
        ],
        [_button("🏘 Community", ACTION_OPEN_COMMUNITY, community_id)],
    ]
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_REVIEW))


def review_result_markup(community_id: str, job_id: str | None = None):
    rows = [[_button("🏘 Community", ACTION_OPEN_COMMUNITY, community_id)]]
    if job_id:
        rows.append([_button("📸 Snapshot job", ACTION_JOB_STATUS, job_id)])
    return _inline_markup(
        _with_navigation(rows, back_action=ACTION_OPEN_COMMUNITY, back_parts=[community_id])
    )


def community_actions_markup(community_id: str):
    rows = [
        [_button("📸 Snapshot", ACTION_SNAPSHOT_COMMUNITY, community_id)],
        [
            _button("👥 Members", ACTION_COMMUNITY_MEMBERS, community_id, "0"),
            _button("💬 Engagement", ACTION_ENGAGEMENT_SETTINGS_OPEN, community_id),
        ],
        [_button("🔄 Refresh", ACTION_OPEN_COMMUNITY, community_id)],
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
    rows = []
    try:
        rows.append([_button("🔄 Refresh job", ACTION_JOB_STATUS, job_id)])
    except ValueError:
        rows = []
    return _inline_markup(_with_navigation(rows, back_action=ACTION_DISC_ACTIVITY))
