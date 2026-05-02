# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from .runtime_base import *
from .runtime_context import *
from .runtime_markup import *
from .runtime_io import *
from .runtime_access import *
from .runtime_parsing import *
from .runtime_topic_brief_style import (
    TOPIC_BRIEF_WIZARD_RULE_NAME,
    _apply_topic_brief_style_target,
    _ensure_topic_brief_style_target,
    _load_topic_brief_style_targets,
    _topic_brief_has_guidance,
    _topic_brief_rule_text,
)
from .ui_common import _button, _inline_markup

_TOPIC_CREATE_STEP_ORDER = (
    "name",
    "description",
    "stance_guidance",
    "style_guidance",
    "example_good_replies",
    "example_bad_replies",
    "avoid_rules",
)
_TOPIC_CREATE_OPTIONAL_STEPS = {
    "style_guidance",
    "example_good_replies",
    "example_bad_replies",
    "avoid_rules",
}
_TOPIC_CREATE_REVIEW_STEP_DETAILS = {
    "example_good_replies_review": (
        "example_good_replies",
        "Continue",
    ),
    "example_bad_replies_review": (
        "example_bad_replies",
        "Done reviewing examples",
    ),
}


def _split_topic_examples(raw_text: str) -> list[str]:
    examples = []
    for chunk in raw_text.replace("\r\n", "\n").split("\n\n"):
        cleaned = " ".join(chunk.strip().split())
        if cleaned:
            examples.append(cleaned)
    return examples


def _merge_topic_examples(existing: list[str], additions: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for example in [*existing, *additions]:
        key = example.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(example)
    return merged


async def _preview_topic_create_sample(
    update: Any,
    context: Any,
    *,
    preview_source: str = "sample",
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "topic_create" or not isinstance(pending.parsed_value, dict):
        await _callback_reply(update, "Finish the draft brief before testing a sample post.")
        return
    client = _api_client(context)
    try:
        prompts = await client.list_engagement_prompt_profiles(limit=20, offset=0)
        profiles = prompts.get("items") or []
        active = next((item for item in profiles if item.get("active")), None)
        profile = active or (profiles[0] if profiles else None)
        if profile is None:
            await _callback_reply(update, "No drafting profile is available for sample preview yet.")
            return
        preview_candidate = None
        source_note = "Source context: synthetic sample post."
        if preview_source == "real":
            preview_candidate = await _load_topic_preview_candidate(
                context,
                operator_id=operator_id,
                pending=pending,
            )
            if preview_candidate is None:
                await _edit_callback_message(
                    update,
                    "Draft brief test unavailable.\n\n"
                    "No collected post is available for a real-post preview yet. "
                    "Try Test sample, or collect reply candidates for this community first.",
                    reply_markup=await _topic_create_confirmation_markup(context, pending),
                )
                return
            source_note = (
                "Source context: real collected post from "
                + str(preview_candidate.get("community_title") or "a collected community")
                + "."
            )
        preview = await client.preview_engagement_prompt_profile(
            str(profile.get("id")),
            variables=_topic_preview_variables(
                pending.parsed_value,
                preview_candidate=preview_candidate,
            ),
        )
    except BotApiError as exc:
        await _edit_callback_message(
            update,
            "Draft brief test unavailable.\n\n"
            + format_api_error(exc.message)
            + "\n\nRevise the brief, save later, or try the sample preview again.",
            reply_markup=await _topic_create_confirmation_markup(context, pending),
        )
        return
    await _edit_callback_message(
        update,
        "Draft brief test\n"
        "Preview only. This does not approve or send anything.\n"
        + source_note
        + "\n\n"
        + format_engagement_prompt_preview(preview),
        reply_markup=await _topic_create_confirmation_markup(context, pending),
    )


async def _load_topic_preview_candidate(
    context: Any,
    *,
    operator_id: int,
    pending: PendingEdit,
) -> dict[str, Any] | None:
    client = _api_client(context)
    filters = _topic_preview_candidate_filters(context, operator_id=operator_id, pending=pending)
    for status in ("needs_review", "approved"):
        data = await client.list_engagement_candidates(
            status=status,
            limit=5,
            offset=0,
            **filters,
        )
        items = data.get("items") or []
        for candidate in items:
            if str(candidate.get("source_excerpt") or "").strip():
                return dict(candidate)
    return None


def _topic_preview_candidate_filters(
    context: Any,
    *,
    operator_id: int,
    pending: PendingEdit,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if pending.object_id and pending.object_id != "new":
        filters["topic_id"] = pending.object_id
    wizard_return_store = context.application.bot_data.get(WIZARD_RETURN_STORE_KEY) or {}
    wizard_state = wizard_return_store.get(operator_id)
    if isinstance(wizard_state, dict):
        community_id = str(wizard_state.get("community_id") or "").strip()
        if community_id:
            filters["community_id"] = community_id
        topic_id = str(wizard_state.get("topic_id") or "").strip()
        if topic_id and "topic_id" not in filters:
            filters["topic_id"] = topic_id
    return filters


def _topic_create_step_index(step: str | None) -> int:
    try:
        return _TOPIC_CREATE_STEP_ORDER.index(
            _topic_create_normalized_step(step) or _TOPIC_CREATE_STEP_ORDER[0]
        )
    except ValueError:
        return 0


def _topic_create_previous_step(step: str | None) -> str:
    if step == "confirm":
        return _TOPIC_CREATE_STEP_ORDER[-1]
    if step == "example_good_replies_review":
        return "example_good_replies"
    if step == "example_bad_replies_review":
        return "example_bad_replies"
    index = _topic_create_step_index(step)
    return _TOPIC_CREATE_STEP_ORDER[max(index - 1, 0)]


def _topic_create_normalized_step(step: str | None) -> str:
    if step in _TOPIC_CREATE_REVIEW_STEP_DETAILS:
        return _TOPIC_CREATE_REVIEW_STEP_DETAILS[step][0]
    return step or _TOPIC_CREATE_STEP_ORDER[0]


def _topic_create_example_advance_label(step: str, state: dict[str, Any]) -> str | None:
    if step == "example_good_replies" and state.get("example_good_replies"):
        return "Continue"
    if step == "example_bad_replies" and state.get("example_bad_replies"):
        return "Done reviewing examples"
    return None


def _topic_create_step_markup(step: str | None, state: dict[str, Any]):
    current_step = step or _TOPIC_CREATE_STEP_ORDER[0]
    normalized_step = _topic_create_normalized_step(current_step)
    if current_step in _TOPIC_CREATE_REVIEW_STEP_DETAILS:
        return engagement_topic_brief_example_markup(
            allow_back=_topic_create_step_index(current_step) > 0,
            advance_label=_TOPIC_CREATE_REVIEW_STEP_DETAILS[current_step][1],
        )
    advance_label = _topic_create_example_advance_label(normalized_step, state)
    return engagement_topic_brief_step_markup(
        allow_back=_topic_create_step_index(current_step) > 0,
        allow_skip=normalized_step in _TOPIC_CREATE_OPTIONAL_STEPS and advance_label is None,
        advance_label=advance_label,
    )


async def _show_topic_create_pending(
    update: Any,
    pending: PendingEdit,
    *,
    context: Any,
    reply_func: Any,
    notice: str | None = None,
) -> None:
    if pending.flow_step == "confirm" and isinstance(pending.parsed_value, dict):
        text = render_edit_preview(pending)
        markup = await _topic_create_confirmation_markup(context, pending)
    else:
        text = render_edit_request(pending)
        markup = _topic_create_step_markup(pending.flow_step, pending.flow_state or {})
    if notice:
        text = notice + "\n\n" + text
    await reply_func(update, text, reply_markup=markup)


def _topic_create_payload(state: dict[str, Any]) -> dict[str, Any]:
    normalized_state = _ensure_topic_brief_style_target(
        state,
        topic_id=str(state.get("topic_id") or "") or None,
        community_id=str(state.get("community_id") or "") or None,
    )
    return {
        "name": str(state.get("name") or ""),
        "description": str(state.get("description") or ""),
        "stance_guidance": str(state.get("stance_guidance") or ""),
        "trigger_keywords": list(state.get("trigger_keywords") or []),
        "negative_keywords": list(state.get("negative_keywords") or []),
        "example_good_replies": list(state.get("example_good_replies") or []),
        "example_bad_replies": list(state.get("example_bad_replies") or []),
        "style_guidance": str(state.get("style_guidance") or ""),
        "avoid_rules": str(state.get("avoid_rules") or ""),
        "style_rule_id": normalized_state.get("style_rule_id"),
        "style_rule_name": normalized_state.get("style_rule_name"),
        "style_rule_target_mode": normalized_state.get("style_rule_target_mode"),
        "style_rule_scope_type": normalized_state.get("style_rule_scope_type"),
        "style_rule_scope_id": normalized_state.get("style_rule_scope_id"),
        "community_id": normalized_state.get("community_id"),
        "active": True,
    }


async def _topic_create_finish_questions(
    update: Any,
    context: Any,
    *,
    operator_user_id: int | None = None,
    operator_id: int | None = None,
    raw_value: str,
    flow_state: dict[str, Any],
    reply_func: Any,
) -> bool:
    resolved_operator_id = operator_id if operator_id is not None else operator_user_id
    if resolved_operator_id is None:
        await reply_func(update, "Telegram did not include a user ID on this update.")
        return True
    normalized_state = _ensure_topic_brief_style_target(
        flow_state,
        topic_id=str(flow_state.get("topic_id") or "") or None,
        community_id=str(flow_state.get("community_id") or "") or None,
    )
    updated = _config_edit_store(context).set_value(
        resolved_operator_id,
        raw_value=raw_value,
        parsed_value=_topic_create_payload(normalized_state),
        flow_step="confirm",
        flow_state=normalized_state,
    )
    if updated is None:
        await reply_func(update, "That edit expired. Start again when you are ready.")
        return True
    await _show_topic_create_pending(update, updated, context=context, reply_func=reply_func)
    return True


def _topic_create_skip_step(
    context: Any,
    operator_id: int,
    pending: PendingEdit,
) -> PendingEdit | None:
    step = pending.flow_step or _TOPIC_CREATE_STEP_ORDER[0]
    normalized_step = _topic_create_normalized_step(step)
    if normalized_step not in _TOPIC_CREATE_OPTIONAL_STEPS:
        return None
    state = dict(pending.flow_state or {})
    if normalized_step == "style_guidance":
        state["style_guidance"] = ""
        return _config_edit_store(context).set_value(
            operator_id,
            raw_value="-",
            parsed_value=None,
            flow_step="example_good_replies",
            flow_state=state,
        )
    if normalized_step == "example_good_replies":
        if not state.get("example_good_replies"):
            state["example_good_replies"] = []
        return _config_edit_store(context).set_value(
            operator_id,
            raw_value="-",
            parsed_value=None,
            flow_step="example_bad_replies",
            flow_state=state,
        )
    if normalized_step == "example_bad_replies":
        if not state.get("example_bad_replies"):
            state["example_bad_replies"] = []
        return _config_edit_store(context).set_value(
            operator_id,
            raw_value="-",
            parsed_value=None,
            flow_step="avoid_rules",
            flow_state=state,
        )
    state["avoid_rules"] = ""
    return _config_edit_store(context).set_value(
        operator_id,
        raw_value="-",
        parsed_value=_topic_create_payload(state),
        flow_step="confirm",
        flow_state=state,
    )


def _topic_create_add_another_step(
    context: Any,
    operator_id: int,
    pending: PendingEdit,
) -> PendingEdit | None:
    step = pending.flow_step or _TOPIC_CREATE_STEP_ORDER[0]
    if step not in _TOPIC_CREATE_REVIEW_STEP_DETAILS:
        return None
    return _config_edit_store(context).set_value(
        operator_id,
        raw_value=pending.raw_value or "",
        parsed_value=None,
        flow_step=_TOPIC_CREATE_REVIEW_STEP_DETAILS[step][0],
        flow_state=dict(pending.flow_state or {}),
    )


def _topic_create_continue_step(
    context: Any,
    operator_id: int,
    pending: PendingEdit,
) -> PendingEdit | None:
    normalized_step = _topic_create_normalized_step(pending.flow_step)
    state = dict(pending.flow_state or {})
    if normalized_step == "example_good_replies" and state.get("example_good_replies"):
        return _config_edit_store(context).set_value(
            operator_id,
            raw_value=pending.raw_value or "",
            parsed_value=None,
            flow_step="example_bad_replies",
            flow_state=state,
        )
    if normalized_step == "example_bad_replies" and state.get("example_bad_replies"):
        return _config_edit_store(context).set_value(
            operator_id,
            raw_value=pending.raw_value or "",
            parsed_value=None,
            flow_step="avoid_rules",
            flow_state=state,
        )
    return None


def _topic_create_step_back(
    context: Any,
    operator_id: int,
    pending: PendingEdit,
) -> PendingEdit | None:
    previous_step = _topic_create_previous_step(pending.flow_step)
    return _config_edit_store(context).set_value(
        operator_id,
        raw_value=pending.raw_value or "",
        parsed_value=None if previous_step != "confirm" else pending.parsed_value,
        flow_step=previous_step,
        flow_state=dict(pending.flow_state or {}),
    )


def _topic_create_saved_for_later_message(pending: PendingEdit) -> str:
    step = pending.flow_step or _TOPIC_CREATE_STEP_ORDER[0]
    step_titles = {
        "name": "Step 1 of 7: Topic name",
        "description": "Step 2 of 7: Conversation target",
        "stance_guidance": "Step 3 of 7: Reply position",
        "style_guidance": "Step 4 of 7: Voice and style",
        "example_good_replies": "Step 5 of 7: Good reply examples",
        "example_good_replies_review": "Step 5 of 7: Good reply examples",
        "example_bad_replies": "Step 6 of 7: Bad reply examples",
        "example_bad_replies_review": "Step 6 of 7: Bad reply examples",
        "avoid_rules": "Step 7 of 7: Avoid rules",
        "confirm": "Review Draft brief",
    }
    title = step_titles.get(step, step_titles["name"])
    lines = [
        "Saved this draft brief for later.",
        f"Current step: {title}",
        "Resume it from Create topic brief or the topic's Draft brief button before it expires.",
        "Use /cancel_edit if you want to discard it instead.",
    ]
    return "\n".join(lines)


async def _topic_create_confirmation_markup(context: Any, pending: PendingEdit):
    if pending.entity != "topic_create" or not isinstance(pending.parsed_value, dict):
        return engagement_topic_brief_confirmation_markup()
    payload = pending.parsed_value
    guidance_present = _topic_brief_has_guidance(
        str(payload.get("style_guidance") or ""),
        str(payload.get("avoid_rules") or ""),
    )
    rows: list[list[Any]] = [[_button("Save brief", ACTION_CONFIG_EDIT_SAVE)]]
    rows.append(
        [
            _button("Test sample", ACTION_ENGAGEMENT_TOPIC_PREVIEW),
            _button("Test real post", ACTION_ENGAGEMENT_TOPIC_PREVIEW, "real"),
        ]
    )
    if guidance_present:
        rows.extend(await _topic_create_style_target_rows(context, pending))
    nav_row = [_button("Back", ACTION_ENGAGEMENT_TOPIC_BRIEF, "nav", "back")]
    nav_row.append(_button("Save later", ACTION_ENGAGEMENT_TOPIC_BRIEF, "nav", "later"))
    nav_row.append(_button("Cancel", ACTION_CONFIG_EDIT_CANCEL))
    rows.append(nav_row)
    return _inline_markup(rows)


async def _topic_create_style_target_rows(context: Any, pending: PendingEdit) -> list[list[Any]]:
    client = _api_client(context)
    state = dict(pending.flow_state or {})
    topic_id = pending.object_id if pending.object_id != "new" else None
    community_id = str(state.get("community_id") or "") or None
    choices = await _load_topic_brief_style_targets(
        client,
        topic_id=topic_id,
        community_id=community_id,
    )
    current_key = _topic_create_style_target_key(
        pending.parsed_value if isinstance(pending.parsed_value, dict) else {}
    )
    buttons: list[Any] = []
    rows: list[list[Any]] = []
    for choice in choices:
        key = _topic_create_style_target_key(choice)
        label = str(choice.get("label") or "Style target")
        if key == current_key:
            label = f"* {label}"
        callback = tuple(str(part) for part in choice.get("callback") or ())
        buttons.append(_button(label, ACTION_ENGAGEMENT_TOPIC_BRIEF, *callback))
        if len(buttons) == 2:
            rows.append(buttons)
            buttons = []
    if buttons:
        rows.append(buttons)
    return rows


def _topic_create_style_target_key(data: dict[str, Any]) -> str:
    target_mode = str(data.get("style_rule_target_mode") or data.get("target_mode") or "wizard")
    if target_mode == "existing":
        return "existing:" + str(data.get("style_rule_id") or "")
    return "wizard:" + str(data.get("style_rule_scope_type") or data.get("scope_type") or "topic")


async def _handle_topic_brief_scope_choice(
    update: Any,
    context: Any,
    *,
    scope_type: str,
) -> None:
    if scope_type not in {"topic", "community"}:
        await _callback_reply(update, "That style-rule target is not available.")
        return
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "topic_create":
        await _callback_reply(update, "No draft brief is waiting right now.")
        return
    state = dict(pending.flow_state or {})
    if scope_type == "community" and not str(state.get("community_id") or "").strip():
        await _callback_reply(update, "Community-scoped guidance is only available from Add engagement.")
        return
    updated_state = _apply_topic_brief_style_target(
        state,
        {
            "target_mode": "wizard",
            "scope_type": scope_type,
            "scope_id": (
                (str(state.get("community_id") or "").strip() or None)
                if scope_type == "community"
                else None
            ),
            "style_rule_id": None,
            "style_rule_name": TOPIC_BRIEF_WIZARD_RULE_NAME,
        },
    )
    updated_state = _ensure_topic_brief_style_target(
        updated_state,
        topic_id=pending.object_id if pending.object_id != "new" else None,
        community_id=str(updated_state.get("community_id") or "") or None,
    )
    updated = _config_edit_store(context).set_value(
        operator_id,
        raw_value=pending.raw_value or "",
        parsed_value=_topic_create_payload(updated_state),
        flow_step="confirm",
        flow_state=updated_state,
    )
    if updated is None:
        await _callback_reply(update, "That draft brief expired. Start again when you are ready.")
        return
    await _show_topic_create_pending(update, updated, context=context, reply_func=_callback_reply)


async def _handle_topic_brief_existing_rule_choice(
    update: Any,
    context: Any,
    *,
    rule_id: str,
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "topic_create":
        await _callback_reply(update, "No draft brief is waiting right now.")
        return
    client = _api_client(context)
    state = dict(pending.flow_state or {})
    choices = await _load_topic_brief_style_targets(
        client,
        topic_id=pending.object_id if pending.object_id != "new" else None,
        community_id=str(state.get("community_id") or "") or None,
    )
    selected = next((choice for choice in choices if str(choice.get("style_rule_id") or "") == rule_id), None)
    if selected is None:
        await _callback_reply(update, "That existing style rule is no longer available for this draft brief.")
        return
    updated_state = _apply_topic_brief_style_target(state, selected)
    updated_state = _ensure_topic_brief_style_target(
        updated_state,
        topic_id=pending.object_id if pending.object_id != "new" else None,
        community_id=str(updated_state.get("community_id") or "") or None,
    )
    updated = _config_edit_store(context).set_value(
        operator_id,
        raw_value=pending.raw_value or "",
        parsed_value=_topic_create_payload(updated_state),
        flow_step="confirm",
        flow_state=updated_state,
    )
    if updated is None:
        await _callback_reply(update, "That draft brief expired. Start again when you are ready.")
        return
    await _show_topic_create_pending(update, updated, context=context, reply_func=_callback_reply)


def _topic_preview_variables(
    payload: dict[str, Any],
    *,
    preview_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    topic_name = str(payload.get("name") or "Draft topic")
    description = str(payload.get("description") or "")
    if preview_candidate is None:
        community = {
            "title": "Sample community",
            "username": "sample_community",
            "description": "A public community for testing draft previews.",
        }
        source_text = (
            f"We are comparing options around {payload.get('name') or 'this topic'}. "
            "What should we evaluate first?"
        )
        source_post = {
            "tg_message_id": 999,
            "text": source_text,
            "message_date": "2026-04-30T12:00:00+00:00",
        }
        reply_context = "The thread asks for practical tradeoffs rather than a product pitch."
        community_context = {
            "latest_summary": "Members are comparing tools and implementation tradeoffs.",
            "dominant_themes": ["comparison", "migration", topic_name.casefold()],
        }
    else:
        source_text = str(preview_candidate.get("source_excerpt") or "").strip()
        community_title = str(preview_candidate.get("community_title") or "Collected community")
        community = {
            "title": community_title,
            "username": "",
            "description": f"A collected public community used for real-post draft preview: {community_title}.",
        }
        source_post = {
            "tg_message_id": preview_candidate.get("source_tg_message_id") or 999,
            "text": source_text,
            "message_date": preview_candidate.get("source_message_date") or "2026-04-30T12:00:00+00:00",
        }
        reply_context = str(preview_candidate.get("detected_reason") or "").strip()
        if not reply_context:
            reply_context = "This collected post was chosen as a realistic draft-preview input."
        community_context = {
            "latest_summary": f"Using collected discussion context from {community_title}.",
            "dominant_themes": ["collected-post", topic_name.casefold()],
        }
    style_rule_text = _topic_brief_rule_text(
        str(payload.get("style_guidance") or ""),
        str(payload.get("avoid_rules") or ""),
    )
    style_scope_type = str(payload.get("style_rule_scope_type") or "topic")
    style_buckets = {
        "global": [],
        "account": [],
        "community": [],
        "topic": [],
    }
    if style_rule_text:
        target_bucket = "community" if style_scope_type == "community" else "topic"
        style_buckets[target_bucket].append(style_rule_text)
    return {
        "community": community,
        "topic": {
            "name": topic_name,
            "description": description,
            "stance_guidance": str(payload.get("stance_guidance") or ""),
            "trigger_keywords": list(payload.get("trigger_keywords") or []),
            "negative_keywords": list(payload.get("negative_keywords") or []),
            "example_good_replies": list(payload.get("example_good_replies") or []),
            "example_bad_replies": list(payload.get("example_bad_replies") or []),
        },
        "style": style_buckets,
        "source_post": source_post,
        "reply_context": reply_context,
        "messages": [source_post],
        "community_context": community_context,
    }


__all__ = [
    "_TOPIC_CREATE_STEP_ORDER",
    "_split_topic_examples",
    "_merge_topic_examples",
    "_preview_topic_create_sample",
    "_topic_create_normalized_step",
    "_show_topic_create_pending",
    "_topic_create_finish_questions",
    "_topic_create_saved_for_later_message",
    "_topic_create_step_back",
    "_topic_create_skip_step",
    "_topic_create_add_another_step",
    "_topic_create_continue_step",
    "_topic_create_confirmation_markup",
    "_handle_topic_brief_scope_choice",
    "_handle_topic_brief_existing_rule_choice",
]
