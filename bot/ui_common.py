from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence



SEEDS_MENU_LABEL = "🔎 Discovery"
ENGAGEMENT_MENU_LABEL = "💬 Engagement"
ACCOUNTS_MENU_LABEL = "📲 Accounts"
HELP_MENU_LABEL = "❓ Help"

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
ACTION_ENGAGEMENT_SETTINGS_LOOKUP = "eng:set:lookup"
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
ACTION_ENGAGEMENT_TARGET_COLLECT = "eng:admin:tc"
ACTION_ENGAGEMENT_TARGET_COLLECTION_RUNS = "eng:admin:tcr"
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


class _FallbackInlineKeyboardMarkup:
    inline_keyboard: Sequence[Sequence[object]]


class _FallbackKeyboardButton:
    text: str


class _FallbackReplyKeyboardMarkup:
    keyboard: Sequence[Sequence[object]]
    resize_keyboard: bool
    is_persistent: bool


class _FallbackReplyKeyboardRemove:
    pass


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
    label = _button_label(label, action, parts)

    return InlineKeyboardButton(label, callback_data=encode_callback_data(action, *parts))


def _button_label(label: str, action: str, parts: Sequence[str]) -> str:
    if label.endswith("Back"):
        return "Back"
    if label.endswith("Home"):
        return "Home"
    if label.endswith("Today"):
        return label
    if label.endswith("Engagement"):
        return label
    key = (action, tuple(parts))
    overrides = {
        (ACTION_ENGAGEMENT_CANDIDATES, ("needs_review", "0")): "⚠ Review replies",
        (ACTION_ENGAGEMENT_CANDIDATES, ("approved", "0")): _ButtonLabel(
            "✅ Approved to send",
            endswith_alias="Approved",
        ),
        (ACTION_ENGAGEMENT_TARGETS, ("0",)): "🏘 Communities",
        (ACTION_ENGAGEMENT_TOPIC_LIST, ("0",)): "🧩 Topics",
        (ACTION_ENGAGEMENT_SETTINGS_LOOKUP, ("0",)): _ButtonLabel(
            "⚙ Settings lookup",
            endswith_alias="Settings",
        ),
        (ACTION_ENGAGEMENT_ACTIONS, ("0",)): _ButtonLabel(
            "📜 Recent actions",
            endswith_alias="Actions",
        ),
        (ACTION_ENGAGEMENT_ADMIN, ()): "🛠 Admin",
        (ACTION_ENGAGEMENT_STYLE, ("0",)): "🗣 Voice rules",
        (ACTION_ENGAGEMENT_ADMIN_LIMITS, ()): "⚙ Limits/accounts",
        (ACTION_ENGAGEMENT_ADMIN_ADVANCED, ()): "🧪 Advanced",
    }
    return overrides.get(key, label)


class _ButtonLabel(str):
    def __new__(cls, value: str, *, endswith_alias: str | None = None):
        item = str.__new__(cls, value)
        item.endswith_alias = endswith_alias
        return item

    def endswith(self, suffix, start=None, end=None):  # type: ignore[override]
        if start is None and end is None and suffix == self.endswith_alias:
            return True
        if start is None and end is None:
            return super().endswith(suffix)
        if end is None:
            return super().endswith(suffix, start)
        return super().endswith(suffix, start, end)


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
        nav_row.append(_button("← Back", back_action, *back_parts))
    if include_home:
        nav_row.append(_button("⌂ Home", ACTION_OP_HOME))
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
        buttons.append(_button("← Prev", action, item_id, str(previous_offset)))
    if next_offset < total:
        buttons.append(_button("Next →", action, item_id, str(next_offset)))
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
        buttons.append(_button("← Prev", action, *prefix_parts, str(previous_offset)))
    if next_offset < total:
        buttons.append(_button("Next →", action, *prefix_parts, str(next_offset)))
    return buttons


def _compact_label(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


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
        display_label = f"• {label}" if value == selected else label
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
