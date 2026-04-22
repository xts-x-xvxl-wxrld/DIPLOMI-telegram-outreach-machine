# ruff: noqa: F401,F403,F405
from __future__ import annotations

from backend.workers.engagement_detect_types import *


def _build_model_input(
    *,
    community: Community,
    topic: EngagementTopic,
    source_message: DetectionMessage,
    community_context: CommunityContext,
    style_rules: dict[str, list[str]],
    semantic_match: SemanticTriggerMatch | None = None,
) -> dict[str, Any]:
    source_post = {
        "tg_message_id": source_message.tg_message_id,
        "text": _truncate_text(source_message.text, MAX_MESSAGE_CHARS),
        "message_date": source_message.message_date.isoformat() if source_message.message_date else None,
        "reply_context": _truncate_text(source_message.reply_context, MAX_MESSAGE_CHARS)
        if source_message.reply_context
        else None,
    }
    model_input: dict[str, Any] = {
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
) -> dict[str, Any]:
    profile = prompt_selection.profile
    version = prompt_selection.version
    fallback = prompt_selection.fallback
    if profile is None:
        assert fallback is not None
        template = fallback.user_prompt_template
        rendered = render_prompt_template(template, model_input)
        return {
            "prompt_profile_id": None,
            "prompt_profile_version_id": None,
            "profile_name": fallback.profile_name,
            "version_number": None,
            "model": fallback_model,
            "temperature": fallback.temperature,
            "max_output_tokens": fallback.max_output_tokens,
            "system_prompt": DETECTION_INSTRUCTIONS,
            "rendered_user_prompt": rendered,
        }

    rendered = render_prompt_template(profile.user_prompt_template, model_input)
    return {
        "prompt_profile_id": profile.id,
        "prompt_profile_version_id": version.id if version is not None else None,
        "profile_name": profile.name,
        "version_number": version.version_number if version is not None else None,
        "model": profile.model,
        "temperature": profile.temperature,
        "max_output_tokens": profile.max_output_tokens,
        "system_prompt": profile.system_prompt,
        "rendered_user_prompt": rendered,
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


def _serialized_size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=True, default=str).encode("utf-8"))


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
]
