from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


SEEDS_MENU_LABEL = "Seed Groups"
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
        [KeyboardButton(SEEDS_MENU_LABEL), KeyboardButton(ACCOUNTS_MENU_LABEL)],
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
