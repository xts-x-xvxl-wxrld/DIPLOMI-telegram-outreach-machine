from __future__ import annotations

from .ui_common import (
    ACTION_ENGAGEMENT_HOME,
    ACTION_ENGAGEMENT_TOPIC_CREATE,
    ACTION_ENGAGEMENT_TOPIC_EDIT,
    ACTION_ENGAGEMENT_TOPIC_EXAMPLE_ADD,
    ACTION_ENGAGEMENT_TOPIC_EXAMPLE_REMOVE,
    ACTION_ENGAGEMENT_TOPIC_LIST,
    ACTION_ENGAGEMENT_TOPIC_OPEN,
    ACTION_ENGAGEMENT_TOPIC_TOGGLE,
    _button,
    compact_topic_edit_field,
    _inline_markup,
    _offset_pager_row,
    _with_navigation,
)


def engagement_topic_pager_markup(
    *,
    offset: int,
    total: int,
    page_size: int,
    can_manage: bool = True,
):
    rows = []
    if can_manage:
        rows.append([_button("➕ Create topic", ACTION_ENGAGEMENT_TOPIC_CREATE)])
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
                    _button(
                        "Edit guidance",
                        ACTION_ENGAGEMENT_TOPIC_EDIT,
                        topic_id,
                        compact_topic_edit_field("stance_guidance"),
                    ),
                    _button(
                        "Edit triggers",
                        ACTION_ENGAGEMENT_TOPIC_EDIT,
                        topic_id,
                        compact_topic_edit_field("trigger_keywords"),
                    ),
                ],
                [
                    _button(
                        "Edit negatives",
                        ACTION_ENGAGEMENT_TOPIC_EDIT,
                        topic_id,
                        compact_topic_edit_field("negative_keywords"),
                    ),
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


__all__ = ["engagement_topic_actions_markup", "engagement_topic_pager_markup"]
