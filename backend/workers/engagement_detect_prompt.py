# ruff: noqa: F401,F403,F405
from __future__ import annotations

from backend.workers.engagement_detect_types import *

CONTINUATION_SYSTEM_ADDENDUM = """Continuation mode:

You are writing a public follow-up reply inside an already-started Telegram thread.
This is not a cold open and not a fresh pitch.

Your job is to continue the conversation naturally and move it forward by one useful step.

Priorities:
- Answer the latest question, concern, or objection first.
- Stay consistent with what the managed account already said earlier in this thread.
- Build on the existing conversation instead of restarting from zero.
- Prefer direct, concrete clarification over broad marketing language.
- Add only one new useful step at a time: clarify, compare, answer, exemplify, or narrow the discussion.
- If the best move is to acknowledge uncertainty, ask one clarifying question, or stop, do that.

Do:
- sound natural, brief, and public-thread appropriate
- directly address the newest reply in the thread
- reuse the thread context to avoid repetition
- keep momentum without overexplaining

Do not:
- repeat the same pitch or recommendation unless needed for clarity
- ignore the latest reply and fall back to generic topic commentary
- make stronger claims than earlier messages support
- continue the thread if the reply would feel forced, repetitive, or off-topic

A good continuation reply should feel like a believable next turn in the same conversation, not a new outreach attempt.
Return structured output only."""


def _build_model_input(
    *,
    community: Community,
    topic: EngagementTopic,
    source_message: DetectionMessage,
    community_context: CommunityContext,
    style_rules: dict[str, list[str]],
    semantic_match: SemanticTriggerMatch | None = None,
    thread_context: ThreadPromptContext | None = None,
    opportunity_kind: str = "root",
) -> dict[str, Any]:
    source_post = {
        "tg_message_id": source_message.tg_message_id,
        "reply_to_tg_message_id": source_message.reply_to_tg_message_id,
        "text": _truncate_text(source_message.text, MAX_MESSAGE_CHARS),
        "message_date": source_message.message_date.isoformat() if source_message.message_date else None,
        "reply_context": _truncate_text(source_message.reply_context, MAX_MESSAGE_CHARS)
        if source_message.reply_context
        else None,
    }
    model_input: dict[str, Any] = {
        "opportunity_kind": opportunity_kind,
        "community": {
            "id": str(community.id),
            "title": community.title,
            "username": community.username,
            "description": community.description,
            "is_group": bool(community.is_group),
        },
        "topic": {
            "id": str(topic.id),
            "name": topic.name,
            "description": topic.description,
            "stance_guidance": topic.stance_guidance,
            "trigger_keywords": list(topic.trigger_keywords or []),
            "negative_keywords": list(topic.negative_keywords or []),
            "example_good_replies": list(topic.example_good_replies or []),
            "example_bad_replies": list(topic.example_bad_replies or []),
        },
        "source_post": source_post,
        "reply_context": _truncate_text(source_message.reply_context, MAX_MESSAGE_CHARS)
        if source_message.reply_context
        else None,
        # Keep a single-message compatibility alias for older prompt templates during the transition.
        "messages": [source_post],
        "style": style_rules,
        "community_context": {
            "latest_summary": _truncate_text(community_context.latest_summary, 2000)
            if community_context.latest_summary
            else None,
            "dominant_themes": community_context.dominant_themes[:20],
        },
    }
    if thread_context is not None:
        model_input["thread"] = {
            "stage": thread_context.stage,
            "objective": thread_context.objective,
            "unresolved_question": _truncate_text(thread_context.unresolved_question, MAX_MESSAGE_CHARS)
            if thread_context.unresolved_question
            else None,
            "avoid_repeating": [_truncate_text(item, 200) for item in thread_context.avoid_repeating[:4]],
            "last_managed_reply": _truncate_text(thread_context.last_managed_reply, 800)
            if thread_context.last_managed_reply
            else None,
            "recent_replies": [_truncate_text(item, MAX_MESSAGE_CHARS) for item in thread_context.recent_replies[:4]],
            "summary": _truncate_text(thread_context.summary, 1000) if thread_context.summary else None,
        }
    semantic_summary = _semantic_match_for_model_input(semantic_match)
    if semantic_summary is not None:
        model_input["semantic_match"] = semantic_summary
    return model_input


async def _load_style_bundle(
    session: AsyncSession,
    *,
    account_id: Any,
    community_id: Any,
    topic_id: Any,
) -> dict[str, list[str]]:
    try:
        bundle = await list_active_style_rules_for_prompt(
            session,
            account_id=account_id,
            community_id=community_id,
            topic_id=topic_id,
        )
    except AttributeError:
        return {"global": [], "account": [], "community": [], "topic": []}
    return bundle.to_dict()


def _build_prompt_runtime(
    model_input: dict[str, Any],
    *,
    prompt_selection: Any,
    fallback_model: str,
    draft_update_context: Any | None = None,
) -> dict[str, Any]:
    profile = prompt_selection.profile
    version = prompt_selection.version
    fallback = prompt_selection.fallback
    if profile is None:
        assert fallback is not None
        return {
            "prompt_profile_id": None,
            "prompt_profile_version_id": None,
            "profile_name": fallback.profile_name,
            "version_number": None,
            "model": fallback_model,
            "temperature": fallback.temperature,
            "max_output_tokens": fallback.max_output_tokens,
            "system_prompt": _system_prompt_with_runtime_addenda(DETECTION_INSTRUCTIONS, model_input),
            "rendered_user_prompt": _render_user_prompt(
                fallback.user_prompt_template,
                model_input,
                draft_update_context=draft_update_context,
            ),
        }

    return {
        "prompt_profile_id": profile.id,
        "prompt_profile_version_id": version.id if version is not None else None,
        "profile_name": profile.name,
        "version_number": version.version_number if version is not None else None,
        "model": profile.model,
        "temperature": profile.temperature,
        "max_output_tokens": profile.max_output_tokens,
        "system_prompt": _system_prompt_with_runtime_addenda(profile.system_prompt, model_input),
        "rendered_user_prompt": _render_user_prompt(
            profile.user_prompt_template,
            model_input,
            draft_update_context=draft_update_context,
        ),
    }


def _prompt_render_summary(
    model_input: dict[str, Any],
    *,
    prompt_runtime: dict[str, Any],
) -> dict[str, Any]:
    style = model_input.get("style") if isinstance(model_input.get("style"), dict) else {}
    summary: dict[str, Any] = {
        "profile_name": prompt_runtime.get("profile_name"),
        "version_number": prompt_runtime.get("version_number"),
        "style_rule_counts": {
            "global": len(style.get("global") or []),
            "account": len(style.get("account") or []),
            "community": len(style.get("community") or []),
            "topic": len(style.get("topic") or []),
        },
        "opportunity_kind": model_input.get("opportunity_kind"),
        "message_count": len(model_input.get("messages") or []),
        "source_post_present": isinstance(model_input.get("source_post"), dict),
        "serialized_input_bytes": _serialized_size(_public_model_input(model_input)),
    }
    if isinstance(model_input.get("semantic_match"), dict):
        summary["semantic_match"] = model_input["semantic_match"]
    return summary


def _public_model_input(model_input: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in model_input.items() if not key.startswith("_")}


def _fit_model_input(model_input: dict[str, Any]) -> dict[str, Any]:
    while _serialized_size(model_input) > MAX_MODEL_INPUT_BYTES and model_input["messages"]:
        model_input["messages"].pop()
    return model_input


def _select_source_message(
    messages: list[DetectionMessage],
    source_tg_message_id: int | None = None,
) -> DetectionMessage:
    if source_tg_message_id is not None:
        for message in messages:
            if message.tg_message_id == source_tg_message_id:
                return message
    return max(
        messages,
        key=lambda message: (
            _sortable_datetime(message.message_date),
            message.tg_message_id or -1,
        ),
    )


def _semantic_match_for_model_input(match: SemanticTriggerMatch | None) -> dict[str, Any] | None:
    if match is None:
        return None
    return {
        "embedding_model": match.embedding_model,
        "embedding_dimensions": match.embedding_dimensions,
        "similarity": round(float(match.similarity), 6),
        "threshold": round(float(match.threshold), 6),
        "rank": match.rank,
    }


def _truncate_text(value: str | None, limit: int) -> str:
    sanitized = sanitize_candidate_excerpt(value) or ""
    return sanitized[:limit]


def _render_user_prompt(
    template: str,
    model_input: dict[str, Any],
    *,
    draft_update_context: Any | None = None,
) -> str:
    rendered = render_prompt_template(template, model_input)
    if _is_continuation_model_input(model_input) and "Continuation task:" not in rendered:
        rendered += _continuation_user_prompt_suffix(model_input)
    if draft_update_context is None:
        return rendered
    return rendered + _draft_update_prompt_suffix(draft_update_context)


def _system_prompt_with_runtime_addenda(system_prompt: str, model_input: dict[str, Any]) -> str:
    if not _is_continuation_model_input(model_input):
        return system_prompt
    if "Continuation mode:" in system_prompt:
        return system_prompt
    return system_prompt.rstrip() + "\n\n" + CONTINUATION_SYSTEM_ADDENDUM


def _continuation_user_prompt_suffix(model_input: dict[str, Any]) -> str:
    thread = model_input.get("thread") if isinstance(model_input.get("thread"), dict) else {}
    source_post = model_input.get("source_post") if isinstance(model_input.get("source_post"), dict) else {}
    community_context = (
        model_input.get("community_context")
        if isinstance(model_input.get("community_context"), dict)
        else {}
    )
    return (
        "\n\nContinuation task:\n"
        "Decide whether the latest thread reply should receive a public continuation reply.\n"
        "If yes, draft the next natural public reply for the same thread.\n"
        "Answer the newest message first.\n"
        "Continue the existing conversation instead of restarting it.\n\n"
        f"Current thread stage: {_continuation_field(thread.get('stage'))}\n"
        f"Thread objective: {_continuation_field(thread.get('objective'))}\n"
        f"Unresolved question: {_continuation_field(thread.get('unresolved_question'))}\n"
        "Repetition guard:\n"
        f"{_continuation_list(thread.get('avoid_repeating'))}\n"
        "Previous managed reply:\n"
        f"{_continuation_field(thread.get('last_managed_reply'))}\n"
        "Recent public thread replies:\n"
        f"{_continuation_list(thread.get('recent_replies'))}\n"
        "Latest reply we are considering:\n"
        f"{_continuation_field(source_post.get('text'))}\n"
        f"Latest reply message id: {_continuation_field(source_post.get('tg_message_id'))}\n"
        f"Replying to managed message id: {_continuation_field(source_post.get('reply_to_tg_message_id'))}\n"
        f"Latest reply date: {_continuation_field(source_post.get('message_date'))}\n"
        "Thread summary:\n"
        f"{_continuation_field(thread.get('summary'))}\n"
        "Community context:\n"
        f"{_continuation_field(community_context.get('latest_summary'))}\n"
        "Themes:\n"
        f"{_continuation_list(community_context.get('dominant_themes'))}\n\n"
        "Structured output requirements:\n"
        '- continuation_goal: one of "clarify", "compare", "answer_objection", '
        '"provide_example", "narrow_discussion", or "other"\n'
        "- answered_question: the specific question answered, or null\n"
        "- avoid_repeating: short phrases describing what the reply should not restate\n"
        "Return structured output only."
    )


def _draft_update_prompt_suffix(context: Any) -> str:
    request = getattr(context, "request", None)
    source_candidate = getattr(context, "source_candidate", None)
    edit_request = "" if request is None else str(getattr(request, "edit_request", "") or "")
    previous_reply = ""
    if source_candidate is not None:
        previous_reply = _truncate_text(
            getattr(source_candidate, "final_reply", None)
            or getattr(source_candidate, "suggested_reply", None)
            or "",
            800,
        )
    return (
        "\n\nRevision task:\n"
        "Treat the normal topic, style, and safety guidance above as the base instructions for this rewrite.\n"
        "Revise the previous draft for the same source post instead of starting from a new strategy.\n"
        f"Operator edit request: {edit_request}\n"
        f"Previous draft: {previous_reply}\n"
        "Keep the previous draft's core recommendation, conversion goal, and concrete CTA unless the operator "
        "explicitly asked to change them or they conflict with the safety rules above.\n"
        "Apply the operator's edit request as an overlay on top of the previous draft and the base guidance above.\n"
        "Write a revised public reply that stays grounded in the source post and directly addresses the "
        "operator's requested change.\n"
        "Return structured output only."
    )


def _serialized_size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=True, default=str).encode("utf-8"))


def _is_continuation_model_input(model_input: dict[str, Any]) -> bool:
    return str(model_input.get("opportunity_kind") or "").strip().casefold() == "continuation"


def _continuation_field(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    return text or "-"


def _continuation_list(value: object) -> str:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        if items:
            return "\n".join(f"- {item}" for item in items)
    return "-"


def _sortable_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return _ensure_aware_utc(value)


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

__all__ = [
    "_build_model_input",
    "_load_style_bundle",
    "_build_prompt_runtime",
    "_prompt_render_summary",
    "_public_model_input",
    "_fit_model_input",
    "_select_source_message",
    "_truncate_text",
    "_ensure_aware_utc",
]
