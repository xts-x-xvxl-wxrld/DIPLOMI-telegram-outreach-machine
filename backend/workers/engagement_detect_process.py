# ruff: noqa: F401,F403,F405
from __future__ import annotations

from backend.workers.engagement_detect_types import *

from backend.workers.engagement_detect_samples import *
from backend.workers.engagement_detect_selection import *
from backend.workers.engagement_detect_prompt import *
from backend.workers.engagement_detect_openai import *
from backend.db.enums import EngagementTimeliness
from backend.queue.client import _normalize_job_id
from backend.services.community_engagement_candidates import (
    infer_candidate_timeliness,
    normalize_moment_strength,
    normalize_reply_value,
)


async def process_engagement_detect(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    detector: Detector = detect_with_openai,
    active_topics_fn: TopicLoader = list_active_topics,
    sample_loader: SampleLoader = None,  # type: ignore[assignment]
    context_loader: ContextLoader = None,  # type: ignore[assignment]
    candidate_creator: CandidateCreator = create_engagement_candidate,
    semantic_selector: SemanticSelector = select_semantic_trigger_messages,
    settings: Settings | None = None,
) -> dict[str, object]:
    validated_payload = EngagementDetectPayload.model_validate(payload)
    runtime_settings = settings or get_settings()
    sample_loader = sample_loader or load_recent_detection_samples
    context_loader = context_loader or load_community_context
    allow_stale_candidates = _is_manual_detect_request(validated_payload)
    reply_deadline_minutes = _reply_deadline_minutes(runtime_settings)

    async with session_factory() as session:
        try:
            community = await session.get(Community, validated_payload.community_id)
            if community is None:
                return _skipped("community_not_found", validated_payload.community_id)

            engagement_settings = await get_engagement_settings(
                session,
                validated_payload.community_id,
            )
            if engagement_settings.mode == EngagementMode.DISABLED.value:
                return _skipped("engagement_disabled", validated_payload.community_id)
            if engagement_settings.mode == EngagementMode.OBSERVE.value:
                return _skipped("observe_mode", validated_payload.community_id)
            if not await has_engagement_target_permission(
                session,
                community_id=validated_payload.community_id,
                permission="detect",
            ):
                return _skipped("engagement_target_detect_not_approved", validated_payload.community_id)
            membership = await get_joined_membership_for_send(
                session,
                community_id=validated_payload.community_id,
            )
            if membership is None:
                return _skipped("no_joined_engagement_membership", validated_payload.community_id)
            if membership.joined_at is None:
                return _skipped("missing_joined_at", validated_payload.community_id)

            topics = await active_topics_fn(session)
            if not topics:
                return _skipped("no_active_topics", validated_payload.community_id)

            messages = await sample_loader(
                session,
                community=community,
                collection_run_id=validated_payload.collection_run_id,
                window_minutes=validated_payload.window_minutes,
            )
            if not messages:
                return _skipped("no_recent_samples", validated_payload.community_id)
            eligible_messages = _filter_detection_messages(
                messages,
                joined_at=membership.joined_at,
                reply_only=engagement_settings.reply_only,
            )
            if not eligible_messages:
                return _skipped("no_trigger_opportunities", validated_payload.community_id)

            community_context = await context_loader(session, community=community)
            prompt_selection = await select_active_prompt_profile(session)
            summary = DetectionSummary(community_id=validated_payload.community_id)
            detector_cap_reached = False
            for topic in topics:
                summary.topics_checked += 1
                topic_messages = await _filter_existing_candidate_messages(
                    session,
                    community_id=validated_payload.community_id,
                    topic_id=topic.id,
                    messages=eligible_messages,
                )
                skipped_duplicates = len(eligible_messages) - len(topic_messages)
                if skipped_duplicates:
                    summary.skipped_dedupe += skipped_duplicates

                trigger_candidates = await _select_trigger_candidates(
                    session,
                    community_id=validated_payload.community_id,
                    topic=topic,
                    messages=topic_messages,
                    runtime_settings=runtime_settings,
                    semantic_selector=semantic_selector,
                    semantic_observability=summary.semantic_observability,
                )
                if not trigger_candidates:
                    summary.skipped_no_signal += 1
                    continue

                for trigger_candidate in trigger_candidates:
                    if summary.detector_calls >= runtime_settings.engagement_max_detector_calls_per_run:
                        summary.skipped_detector_cap += 1
                        detector_cap_reached = True
                        break
                    source_message = trigger_candidate.message

                    style_rules = await _load_style_bundle(
                        session,
                        account_id=engagement_settings.assigned_account_id,
                        community_id=validated_payload.community_id,
                        topic_id=topic.id,
                    )
                    model_input = _build_model_input(
                        community=community,
                        topic=topic,
                        source_message=source_message,
                        community_context=community_context,
                        style_rules=style_rules,
                        semantic_match=trigger_candidate.semantic_match,
                    )
                    model_input = _fit_model_input(model_input)
                    prompt_runtime = _build_prompt_runtime(
                        model_input,
                        prompt_selection=prompt_selection,
                        fallback_model=runtime_settings.openai_engagement_model,
                    )
                    model_input["_prompt_runtime"] = prompt_runtime
                    decision = await detector(model_input)
                    decision = EngagementDetectionDecision.model_validate(decision)
                    summary.detector_calls += 1
                    if not decision.should_engage:
                        summary.skipped_no_signal += 1
                        continue
                    if not decision.suggested_reply:
                        summary.skipped_validation += 1
                        continue
                    if (
                        decision.source_tg_message_id is not None
                        and source_message.tg_message_id is not None
                        and decision.source_tg_message_id != source_message.tg_message_id
                    ):
                        summary.skipped_validation += 1
                        continue
                    detected_at = _utcnow()
                    inferred_timeliness = infer_candidate_timeliness(
                        detected_at=detected_at,
                        review_deadline_at=_infer_review_deadline_at(
                            source_message_date=source_message.message_date,
                            detected_at=detected_at,
                            reply_deadline_minutes=reply_deadline_minutes,
                        ),
                        reply_deadline_at=_infer_reply_deadline_at(
                            source_message_date=source_message.message_date,
                            detected_at=detected_at,
                            reply_deadline_minutes=reply_deadline_minutes,
                        ),
                    )
                    if (
                        inferred_timeliness == EngagementTimeliness.STALE.value
                        and not allow_stale_candidates
                    ):
                        summary.skipped_stale += 1
                        continue
                    try:
                        moment_strength = normalize_moment_strength(decision.moment_strength)
                        reply_value = normalize_reply_value(
                            decision.reply_value,
                            has_reply=bool(decision.suggested_reply),
                        )
                    except EngagementValidationError:
                        summary.skipped_validation += 1
                        continue
                    model_output = decision.model_dump(mode="json", exclude_none=True)
                    model_output["moment_strength"] = moment_strength
                    model_output["timeliness"] = inferred_timeliness
                    model_output["reply_value"] = reply_value
                    semantic_summary = _semantic_match_for_storage(trigger_candidate.semantic_match)
                    if semantic_summary is not None:
                        model_output["semantic_match"] = semantic_summary
                    try:
                        creation = await candidate_creator(
                            session,
                            community_id=validated_payload.community_id,
                            topic_id=topic.id,
                            source_tg_message_id=source_message.tg_message_id,
                            source_excerpt=source_message.text,
                            source_message_date=source_message.message_date,
                            detected_reason=decision.reason,
                            suggested_reply=decision.suggested_reply,
                            moment_strength=moment_strength,
                            reply_value=reply_value,
                            model=str(prompt_runtime["model"]),
                            model_output=model_output,
                            risk_notes=decision.risk_notes,
                            prompt_profile_id=prompt_runtime.get("prompt_profile_id"),
                            prompt_profile_version_id=prompt_runtime.get("prompt_profile_version_id"),
                            prompt_render_summary=_prompt_render_summary(
                                model_input,
                                prompt_runtime=prompt_runtime,
                            ),
                            detected_at=detected_at,
                            reply_deadline_minutes=reply_deadline_minutes,
                        )
                    except EngagementValidationError:
                        summary.skipped_validation += 1
                        continue

                    if creation.created:
                        summary.candidates_created += 1
                        if trigger_candidate.semantic_match is not None:
                            summary.semantic_candidates_created += 1
                    else:
                        summary.skipped_dedupe += 1

                if detector_cap_reached:
                    break

            await session.commit()
            result = summary.to_dict()
            LOGGER.info("engagement.detect_summary", extra={"engagement_detect": result})
            return result
        except EngagementServiceError:
            await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise


def run_engagement_detect_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_engagement_detect(payload))


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


def _filter_detection_messages(
    messages: list[DetectionMessage],
    *,
    joined_at: datetime,
    reply_only: bool,
) -> list[DetectionMessage]:
    joined_cutoff = _ensure_aware_utc(joined_at)
    eligible: list[DetectionMessage] = []
    for message in messages:
        if not message.text.strip():
            continue
        if reply_only and message.tg_message_id is None:
            continue
        if message.message_date is None:
            continue
        if _ensure_aware_utc(message.message_date) < joined_cutoff:
            continue
        if not message.is_replyable:
            continue
        eligible.append(message)
    return eligible


async def _filter_existing_candidate_messages(
    session: AsyncSession,
    *,
    community_id: object,
    topic_id: object,
    messages: list[DetectionMessage],
) -> list[DetectionMessage]:
    filtered: list[DetectionMessage] = []
    for message in messages:
        if await _has_active_candidate_duplicate(
            session,
            community_id=community_id,
            topic_id=topic_id,
            source_tg_message_id=message.tg_message_id,
            source_excerpt=message.text,
        ):
            continue
        filtered.append(message)
    return filtered


def _fit_model_input(model_input: dict[str, Any]) -> dict[str, Any]:
    while _serialized_size(model_input) > MAX_MODEL_INPUT_BYTES and model_input["messages"]:
        model_input["messages"].pop()
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


async def _select_trigger_candidates(
    session: AsyncSession,
    *,
    community_id: object,
    topic: EngagementTopic,
    messages: list[DetectionMessage],
    runtime_settings: Settings,
    semantic_selector: SemanticSelector,
    semantic_observability: SemanticSelectionStats | None = None,
) -> list[TriggerCandidate]:
    if not messages:
        return []
    if runtime_settings.engagement_semantic_matching_enabled:
        semantic_matches = await semantic_selector(
            session,
            community_id=community_id,
            topic=topic,
            messages=messages,
            settings=runtime_settings,
            observability=semantic_observability,
        )
        if semantic_matches and semantic_observability is not None:
            semantic_observability.semantic_matches_selected = max(
                semantic_observability.semantic_matches_selected,
                len(semantic_matches),
            )
        if semantic_matches:
            return [
                TriggerCandidate(
                    message=_coerce_detection_message(match.message),
                    semantic_match=match,
                )
                for match in semantic_matches
            ]
        if not (topic.trigger_keywords or []):
            return []
        # Rollout fallback: only exact trigger keywords may rescue an empty semantic selection.
        fallback_messages = _prefilter_messages(topic, messages, require_trigger=True)
        return [TriggerCandidate(message=_select_source_message(fallback_messages))] if fallback_messages else []

    if not (topic.trigger_keywords or []):
        return []
    matching_messages = _prefilter_messages(topic, messages, require_trigger=True)
    return [TriggerCandidate(message=_select_source_message(matching_messages))] if matching_messages else []


def _semantic_match_for_storage(match: SemanticTriggerMatch | None) -> dict[str, Any] | None:
    if match is None:
        return None
    return {
        "model": match.embedding_model,
        "dimensions": match.embedding_dimensions,
        "similarity": round(float(match.similarity), 6),
        "threshold": round(float(match.threshold), 6),
        "rank": match.rank,
    }


def _skipped(reason: str, community_id: object) -> dict[str, object]:
    return {
        "status": "skipped",
        "job_type": "engagement.detect",
        "community_id": str(community_id),
        "reason": reason,
    }


def _is_manual_detect_request(payload: EngagementDetectPayload) -> bool:
    job_id = _current_job_id()
    manual_prefix = _normalize_job_id("engagement.detect.manual:")
    if job_id is not None and manual_prefix is not None and job_id.startswith(manual_prefix):
        return True
    return payload.collection_run_id is None and payload.requested_by is not None


def _reply_deadline_minutes(runtime_settings: object) -> int:
    value = getattr(runtime_settings, "engagement_reply_deadline_minutes", 90)
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return 90


async def detect_with_openai(model_input: dict[str, Any]) -> EngagementDetectionDecision:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError("openai must be installed before engagement.detect can run") from exc

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for engagement.detect")

    prompt_runtime = model_input.get("_prompt_runtime")
    if not isinstance(prompt_runtime, dict):
        prompt_runtime = {}
    model = str(prompt_runtime.get("model") or settings.openai_engagement_model)
    instructions = str(prompt_runtime.get("system_prompt") or DETECTION_INSTRUCTIONS)
    rendered_prompt = str(prompt_runtime.get("rendered_user_prompt") or "")
    if not rendered_prompt:
        rendered_prompt = (
            "Review this compact Telegram community context and decide whether a "
            "short public reply would be genuinely useful. Return structured output only.\n\n"
            f"{json.dumps(_public_model_input(model_input), ensure_ascii=True, default=str)}"
        )
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.parse(
        model=model,
        instructions=instructions,
        input=[
            {
                "role": "user",
                "content": rendered_prompt,
            }
        ],
        text_format=EngagementDetectionDecision,
        temperature=float(prompt_runtime.get("temperature") or 0.2),
        max_output_tokens=int(prompt_runtime.get("max_output_tokens") or 1000),
    )
    decision = response.output_parsed
    if decision is None:
        raise RuntimeError("OpenAI returned no parsed engagement detection decision")
    return decision


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


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _infer_reply_deadline_at(
    *,
    source_message_date: datetime | None,
    detected_at: datetime,
    reply_deadline_minutes: int,
) -> datetime:
    source_time = _ensure_aware_utc(source_message_date or detected_at)
    return source_time + timedelta(minutes=max(reply_deadline_minutes, 1))


def _infer_review_deadline_at(
    *,
    source_message_date: datetime | None,
    detected_at: datetime,
    reply_deadline_minutes: int,
) -> datetime | None:
    if source_message_date is None:
        return None
    return _infer_reply_deadline_at(
        source_message_date=source_message_date,
        detected_at=detected_at,
        reply_deadline_minutes=reply_deadline_minutes,
    ) - timedelta(minutes=30)


async def _has_active_candidate_duplicate(
    session: AsyncSession,
    *,
    community_id: object,
    topic_id: object,
    source_tg_message_id: int | None,
    source_excerpt: str | None,
) -> bool:
    active_statuses = (
        EngagementCandidateStatus.NEEDS_REVIEW.value,
        EngagementCandidateStatus.APPROVED.value,
    )
    query = select(EngagementCandidate).where(
        EngagementCandidate.community_id == community_id,
        EngagementCandidate.topic_id == topic_id,
        EngagementCandidate.status.in_(active_statuses),
    )
    if source_tg_message_id is not None:
        query = query.where(EngagementCandidate.source_tg_message_id == source_tg_message_id)
    else:
        query = query.where(
            EngagementCandidate.source_tg_message_id.is_(None),
            EngagementCandidate.source_excerpt == sanitize_candidate_excerpt(source_excerpt),
        )
    return await session.scalar(query.limit(1)) is not None


def _serialized_size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=True, default=str).encode("utf-8"))


def _public_model_input(model_input: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in model_input.items() if not key.startswith("_")}


def _coerce_detection_message(message: object) -> DetectionMessage:
    if isinstance(message, DetectionMessage):
        return message
    return DetectionMessage(
        tg_message_id=getattr(message, "tg_message_id", None),
        text=str(getattr(message, "text", "") or ""),
        message_date=getattr(message, "message_date", None),
        reply_context=getattr(message, "reply_context", None),
        is_replyable=bool(getattr(message, "is_replyable", True)),
    )


def _prefilter_messages(
    topic: EngagementTopic,
    messages: list[DetectionMessage],
    *,
    require_trigger: bool = False,
) -> list[DetectionMessage]:
    triggers = [keyword.casefold() for keyword in topic.trigger_keywords or [] if keyword]
    negatives = [keyword.casefold() for keyword in topic.negative_keywords or [] if keyword]
    if require_trigger and not triggers:
        return []
    matches: list[DetectionMessage] = []
    for message in messages:
        text = message.text.casefold()
        if (triggers or require_trigger) and not any(keyword in text for keyword in triggers):
            continue
        if negatives and any(keyword in text for keyword in negatives):
            continue
        matches.append(message)
    return matches


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


def _sortable_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return _ensure_aware_utc(value)


def _current_job_id() -> str | None:
    try:
        from rq import get_current_job
    except Exception:
        return None

    job = get_current_job()
    if job is None:
        return None
    return str(job.id)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

__all__ = [
    "process_engagement_detect",
    "run_engagement_detect_job",
]
