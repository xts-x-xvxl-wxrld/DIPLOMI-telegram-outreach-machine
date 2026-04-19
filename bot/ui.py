from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


SEEDS_MENU_LABEL = "Seed Groups"
ENGAGEMENT_MENU_LABEL = "Engagement"
ACCOUNTS_MENU_LABEL = "Accounts"
HELP_MENU_LABEL = "Help"

ACTION_OPEN_SEED_GROUP = "sg"
ACTION_RESOLVE_SEED_GROUP = "sr"
ACTION_SEED_CHANNELS = "sl"
ACTION_SEED_CANDIDATES = "sc"
ACTION_OPEN_COMMUNITY = "cm"
ACTION_APPROVE_COMMUNITY = "ca"
ACTION_REJECT_COMMUNITY = "cr"
ACTION_COLLECT_COMMUNITY = "cl"
ACTION_COMMUNITY_MEMBERS = "mb"
ACTION_JOB_STATUS = "jb"
ACTION_ENGAGEMENT_HOME = "eng:home"
ACTION_ENGAGEMENT_CANDIDATES = "eng:cand:list"
ACTION_ENGAGEMENT_APPROVE = "eng:cand:approve"
ACTION_ENGAGEMENT_REJECT = "eng:cand:reject"
ACTION_ENGAGEMENT_SEND = "eng:cand:send"
ACTION_ENGAGEMENT_CANDIDATE_OPEN = "eng:cand:open"
ACTION_ENGAGEMENT_TOPIC_LIST = "eng:topic:list"
ACTION_ENGAGEMENT_TOPIC_OPEN = "eng:topic:open"
ACTION_ENGAGEMENT_TOPIC_TOGGLE = "eng:topic:toggle"
ACTION_ENGAGEMENT_SETTINGS_OPEN = "eng:set:open"
ACTION_ENGAGEMENT_SETTINGS_PRESET = "eng:set:preset"
ACTION_ENGAGEMENT_SETTINGS_JOIN = "eng:set:join"
ACTION_ENGAGEMENT_SETTINGS_POST = "eng:set:post"
ACTION_ENGAGEMENT_JOIN = "eng:join"
ACTION_ENGAGEMENT_DETECT = "eng:detect"
ACTION_ENGAGEMENT_ACTIONS = "eng:actions:list"


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
    return _inline_markup(
        [
            [_button("Open", ACTION_OPEN_SEED_GROUP, seed_group_id)],
            [
                _button("Resolve", ACTION_RESOLVE_SEED_GROUP, seed_group_id),
                _button("Channels", ACTION_SEED_CHANNELS, seed_group_id, "0"),
            ],
            [_button("Candidates", ACTION_SEED_CANDIDATES, seed_group_id, "0")],
        ]
    )


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
    if not rows:
        return None
    return _inline_markup(rows)


def candidate_actions_markup(community_id: str):
    return _inline_markup(
        [
            [
                _button("Approve", ACTION_APPROVE_COMMUNITY, community_id),
                _button("Reject", ACTION_REJECT_COMMUNITY, community_id),
            ],
            [_button("Community", ACTION_OPEN_COMMUNITY, community_id)],
        ]
    )


def engagement_candidate_actions_markup(candidate_id: str):
    return _inline_markup(
        [
            [
                _button("Approve", ACTION_ENGAGEMENT_APPROVE, candidate_id),
                _button("Reject", ACTION_ENGAGEMENT_REJECT, candidate_id),
            ],
            [_button("More replies", ACTION_ENGAGEMENT_CANDIDATES, "needs_review", "0")],
        ]
    )


def engagement_candidate_send_markup(candidate_id: str):
    return _inline_markup(
        [
            [_button("Queue send", ACTION_ENGAGEMENT_SEND, candidate_id)],
            [_button("Approved replies", ACTION_ENGAGEMENT_CANDIDATES, "approved", "0")],
        ]
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
    if not buttons:
        return None
    return _inline_markup([buttons])


def engagement_home_markup():
    return _inline_markup(
        [
            [
                _button("Topics", ACTION_ENGAGEMENT_TOPIC_LIST, "0"),
                _button("Replies", ACTION_ENGAGEMENT_CANDIDATES, "needs_review", "0"),
            ],
            [_button("Audit", ACTION_ENGAGEMENT_ACTIONS, "0")],
        ]
    )


def engagement_settings_markup(community_id: str, *, allow_join: bool, allow_post: bool):
    return _inline_markup(
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
                _button("Queue join", ACTION_ENGAGEMENT_JOIN, community_id),
                _button("Detect now", ACTION_ENGAGEMENT_DETECT, community_id, "60"),
            ],
        ]
    )


def engagement_topic_pager_markup(
    *,
    offset: int,
    total: int,
    page_size: int,
):
    rows = [[_button("Engagement", ACTION_ENGAGEMENT_HOME)]]
    pager_row = _offset_pager_row(
        action=ACTION_ENGAGEMENT_TOPIC_LIST,
        offset=offset,
        total=total,
        page_size=page_size,
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(rows)


def engagement_topic_actions_markup(topic_id: str, *, active: bool):
    return _inline_markup(
        [
            [
                _button(
                    "Deactivate" if active else "Activate",
                    ACTION_ENGAGEMENT_TOPIC_TOGGLE,
                    topic_id,
                    "0" if active else "1",
                )
            ],
            [_button("Topics", ACTION_ENGAGEMENT_TOPIC_LIST, "0")],
        ]
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
    rows.append([_button("Engagement", ACTION_ENGAGEMENT_HOME)])
    return _inline_markup(rows)


def engagement_action_pager_markup(
    *,
    offset: int,
    total: int,
    page_size: int,
):
    rows = [[_button("Engagement", ACTION_ENGAGEMENT_HOME)]]
    pager_row = _offset_pager_row(
        action=ACTION_ENGAGEMENT_ACTIONS,
        offset=offset,
        total=total,
        page_size=page_size,
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(rows)


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
    return _inline_markup(rows)


def review_result_markup(community_id: str, job_id: str | None = None):
    rows = [[_button("Community", ACTION_OPEN_COMMUNITY, community_id)]]
    if job_id:
        rows.append([_button("Collection Job", ACTION_JOB_STATUS, job_id)])
    return _inline_markup(rows)


def community_actions_markup(community_id: str):
    return _inline_markup(
        [
            [_button("Collect 90d", ACTION_COLLECT_COMMUNITY, community_id)],
            [_button("Members", ACTION_COMMUNITY_MEMBERS, community_id, "0")],
            [_button("Refresh", ACTION_OPEN_COMMUNITY, community_id)],
        ]
    )


def member_pager_markup(
    community_id: str,
    *,
    offset: int,
    total: int,
    page_size: int,
):
    rows = [[_button("Community", ACTION_OPEN_COMMUNITY, community_id)]]
    pager_row = _pager_row(
        action=ACTION_COMMUNITY_MEMBERS,
        item_id=community_id,
        offset=offset,
        total=total,
        page_size=page_size,
    )
    if pager_row:
        rows.append(pager_row)
    return _inline_markup(rows)


def job_actions_markup(job_id: str):
    return _inline_markup([[_button("Refresh Job", ACTION_JOB_STATUS, job_id)]])


def parse_callback_data(data: str) -> tuple[str, list[str]]:
    parts = data.split(":")
    if parts[0] == "eng":
        if len(parts) >= 3 and parts[1] in {"actions", "cand", "set", "topic"}:
            return ":".join(parts[:3]), parts[3:]
        if len(parts) >= 2:
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
