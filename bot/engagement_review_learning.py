# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from .runtime_base import *
from .runtime_markup import *
from .runtime_context import *
from .runtime_access import _reviewer_label, _telegram_user_id
from .runtime_io import _callback_reply, _edit_callback_message, _reply
from .ui import engagement_candidate_style_scope_markup, engagement_style_rule_actions_markup
from .engagement_review_flow import _candidate_detail_context


_EDITED_REPLY_REQUIRED_MESSAGE = (
    "Edit the final reply first, then save that deliberate edit as guidance."
)


def _edited_candidate_reply(candidate: dict[str, Any]) -> str:
    return str(candidate.get("final_reply") or "").strip()


async def _save_candidate_reply_as_good_example(
    update: Any,
    context: Any,
    candidate_id: str,
    *,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    candidate = await client.get_engagement_candidate(candidate_id)
    topic_id = str(candidate.get("topic_id") or "")
    example = _edited_candidate_reply(candidate)
    if not topic_id or not example:
        await _callback_reply(update, _EDITED_REPLY_REQUIRED_MESSAGE)
        return
    topic = await client.add_engagement_topic_example(
        topic_id,
        example_type="good",
        example=example,
        operator_user_id=_telegram_user_id(update),
    )
    refreshed = await _candidate_detail_context(client, candidate_id)
    message = (
        "Saved the current reply as a good example.\n\n"
        + format_engagement_candidate_card(refreshed, detail=True)
        + "\n\n"
        + f"Topic good examples: {len(topic.get('example_good_replies') or [])}"
    )
    reply_markup = _engagement_candidate_detail_markup(candidate_id, refreshed)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _reply(update, message, reply_markup=reply_markup)


def _candidate_style_rule_text(reply_text: str) -> str:
    return (
        "Use this approved reply as a style reference for tone, structure, and level of detail. "
        "Do not copy it word for word.\n\n"
        f"Reference reply:\n{reply_text}"
    )


def _candidate_style_rule_name(candidate: dict[str, Any]) -> str:
    topic_name = str(candidate.get("topic_name") or "").strip()
    community_title = str(candidate.get("community_title") or "").strip()
    if topic_name:
        return f"Reply edit reference: {topic_name}"
    if community_title:
        return f"Reply edit reference: {community_title}"
    return "Reply edit reference"


async def _prompt_candidate_style_rule_scope(
    update: Any,
    context: Any,
    candidate_id: str,
) -> None:
    client = _api_client(context)
    candidate = await client.get_engagement_candidate(candidate_id)
    reply_text = _edited_candidate_reply(candidate)
    if not reply_text:
        await _callback_reply(update, _EDITED_REPLY_REQUIRED_MESSAGE)
        return
    await _edit_callback_message(
        update,
        "Create a style rule from this reply edit.\n\n"
        "Choose where this guidance should apply. The saved rule will keep the reply as a style "
        "reference, not a template to copy word for word.",
        reply_markup=engagement_candidate_style_scope_markup(
            candidate_id,
            allow_global=True,
            allow_community=bool(candidate.get("community_id")),
            allow_topic=bool(candidate.get("topic_id")),
        ),
    )


async def _create_candidate_style_rule(
    update: Any,
    context: Any,
    candidate_id: str,
    *,
    scope_type: str,
) -> None:
    if scope_type not in {"global", "community", "topic"}:
        await _callback_reply(update, "That style-rule scope is not available from this reply.")
        return
    client = _api_client(context)
    candidate = await client.get_engagement_candidate(candidate_id)
    reply_text = _edited_candidate_reply(candidate)
    if not reply_text:
        await _callback_reply(update, _EDITED_REPLY_REQUIRED_MESSAGE)
        return
    scope_id: str | None = None
    if scope_type == "community":
        scope_id = str(candidate.get("community_id") or "") or None
    elif scope_type == "topic":
        scope_id = str(candidate.get("topic_id") or "") or None
    if scope_type != "global" and scope_id is None:
        await _callback_reply(update, f"This reply opportunity does not have a {scope_type} scope to attach that rule to.")
        return
    rule = await client.create_engagement_style_rule(
        scope_type=scope_type,
        scope_id=scope_id,
        name=_candidate_style_rule_name(candidate),
        priority=160,
        rule_text=_candidate_style_rule_text(reply_text),
        created_by=_reviewer_label(update),
        operator_user_id=_telegram_user_id(update),
    )
    scope_label = scope_type if scope_type == "global" else f"{scope_type} {scope_id}"
    await _edit_callback_message(
        update,
        f"Created a {scope_type} style rule from this reply edit.\n\n"
        + format_engagement_style_rule_card(rule, detail=True)
        + f"\n\nSaved scope: {scope_label}",
        reply_markup=engagement_style_rule_actions_markup(
            str(rule.get("id") or "unknown"),
            active=bool(rule.get("active")),
        ),
    )


__all__ = [
    "_save_candidate_reply_as_good_example",
    "_prompt_candidate_style_rule_scope",
    "_create_candidate_style_rule",
]
