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
from backend.services.task_first_engagement_draft_updates import (
    complete_draft_update_request,
    fail_draft_update_request,
    get_draft_update_request_by_id,
    list_draft_update_requests_for_engagement,
)


@dataclass(frozen=True)
class DraftUpdateExecutionContext:
    request: EngagementDraftUpdateRequest
    source_candidate: EngagementCandidate
    topic: EngagementTopic
    source_message: DetectionMessage
    ignored_duplicate_candidate_ids: set[UUID]


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
    draft_update_request_id = validated_payload.draft_update_request_id
    allow_stale_candidates = _is_manual_detect_request(validated_payload) or draft_update_request_id is not None
    reply_deadline_minutes = _reply_deadline_minutes(runtime_settings)
    job_id = _current_job_id() or f"engagement.detect:{validated_payload.community_id}"
    LOGGER.info(
        "Starting engagement detect job_id=%s community_id=%s collection_run_id=%s draft_update_request_id=%s window_minutes=%s allow_stale_candidates=%s",
        job_id,
        validated_payload.community_id,
        validated_payload.collection_run_id,
        draft_update_request_id,
        validated_payload.window_minutes,
        allow_stale_candidates,
    )

    async with session_factory() as session:
        try:
            community = await session.get(Community, validated_payload.community_id)
            if community is None:
                return _skipped("community_not_found", validated_payload.community_id)

            engagement_settings = await get_engagement_settings(
                session,
                validated_payload.community_id,
            )
            draft_update_context = await _load_draft_update_context(
                session,
                community_id=validated_payload.community_id,
                request_id=draft_update_request_id,
            )
            if draft_update_request_id is not None and draft_update_context is None:
                return _skipped("draft_update_request_not_pending", validated_payload.community_id)

            membership = None
            selected_telegram_account_id = engagement_settings.assigned_account_id
            if draft_update_context is None:
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
                selected_telegram_account_id = membership.telegram_account_id

                topics = await active_topics_fn(session)
                if not topics:
                    return _skipped("no_active_topics", validated_payload.community_id)
                LOGGER.info(
                    "Loaded engagement topics job_id=%s community_id=%s topic_count=%s",
                    job_id,
                    validated_payload.community_id,
                    len(topics),
                )

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
                LOGGER.info(
                    "Prepared engagement detect samples job_id=%s community_id=%s sampled_messages=%s eligible_messages=%s reply_only=%s",
                    job_id,
                    validated_payload.community_id,
                    len(messages),
                    len(eligible_messages),
                    engagement_settings.reply_only,
                )
            else:
                topics = [draft_update_context.topic]
                eligible_messages = [draft_update_context.source_message]
                if selected_telegram_account_id is None:
                    membership = await get_joined_membership_for_send(
                        session,
                        community_id=validated_payload.community_id,
                    )
                    if membership is not None:
                        selected_telegram_account_id = membership.telegram_account_id
                LOGGER.info(
                    "Loaded pending draft update context job_id=%s community_id=%s request_id=%s source_candidate_id=%s topic_id=%s",
                    job_id,
                    validated_payload.community_id,
                    draft_update_context.request.id,
                    draft_update_context.source_candidate.id,
                    draft_update_context.topic.id,
                )

            community_context = await context_loader(session, community=community)
            prompt_selection = await select_active_prompt_profile(session)
            summary = DetectionSummary(community_id=validated_payload.community_id)
            detector_cap_reached = False
            for topic in topics:
                summary.topics_checked += 1
                if draft_update_context is None:
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
                        selected_telegram_account_id=selected_telegram_account_id,
                    )
                else:
                    topic_messages = [draft_update_context.source_message]
                    skipped_duplicates = 0
                    trigger_candidates = [TriggerCandidate(message=draft_update_context.source_message)]
                LOGGER.info(
                    "Evaluated engagement topic job_id=%s community_id=%s topic_id=%s topic_messages=%s trigger_candidates=%s skipped_duplicates=%s",
                    job_id,
                    validated_payload.community_id,
                    topic.id,
                    len(topic_messages),
                    len(trigger_candidates),
                    skipped_duplicates,
                )
                if not trigger_candidates:
                    summary.skipped_no_signal += 1
                    if draft_update_context is not None:
                        await _fail_pending_draft_update(
                            session,
                            draft_update_context,
                            reason="no_trigger_candidates",
                            job_id=job_id,
                        )
                    continue

                for trigger_candidate in trigger_candidates:
                    if summary.detector_calls >= runtime_settings.engagement_max_detector_calls_per_run:
                        summary.skipped_detector_cap += 1
                        detector_cap_reached = True
                        LOGGER.info("Detector cap reached job_id=%s community_id=%s topic_id=%s detector_calls=%s max_calls=%s", job_id, validated_payload.community_id, topic.id, summary.detector_calls, runtime_settings.engagement_max_detector_calls_per_run)
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
                        thread_context=trigger_candidate.thread_context,
                        opportunity_kind=(
                            "continuation"
                            if trigger_candidate.thread_context is not None
                            else "root"
                        ),
                    )
                    model_input = _fit_model_input(model_input)
                    prompt_runtime = _build_prompt_runtime(
                        model_input,
                        prompt_selection=prompt_selection,
                        fallback_model=runtime_settings.openai_engagement_model,
                        draft_update_context=draft_update_context,
                    )
                    model_input["_prompt_runtime"] = prompt_runtime
                    decision = await detector(model_input)
                    summary.detector_calls += 1
                    try:
                        decision = EngagementDetectionDecision.model_validate(decision)
                    except ValidationError:
                        summary.skipped_validation += 1
                        LOGGER.info("Detector output failed validation job_id=%s community_id=%s topic_id=%s source_tg_message_id=%s", job_id, validated_payload.community_id, topic.id, source_message.tg_message_id)
                        if draft_update_context is not None:
                            await _fail_pending_draft_update(
                                session,
                                draft_update_context,
                                reason="detector_output_validation_failed",
                                job_id=job_id,
                            )
                        continue
                    LOGGER.info("Detector returned decision job_id=%s community_id=%s topic_id=%s source_tg_message_id=%s should_engage=%s has_reply=%s", job_id, validated_payload.community_id, topic.id, source_message.tg_message_id, decision.should_engage, bool(decision.suggested_reply))
                    if not decision.should_engage:
                        summary.skipped_no_signal += 1
                        if draft_update_context is not None:
                            await _fail_pending_draft_update(
                                session,
                                draft_update_context,
                                reason="detector_declined_rewrite",
                                job_id=job_id,
                            )
                        continue
                    if not decision.suggested_reply:
                        summary.skipped_validation += 1
                        if draft_update_context is not None:
                            await _fail_pending_draft_update(
                                session,
                                draft_update_context,
                                reason="detector_missing_rewrite",
                                job_id=job_id,
                            )
                        continue
                    if (
                        decision.source_tg_message_id is not None
                        and source_message.tg_message_id is not None
                        and decision.source_tg_message_id != source_message.tg_message_id
                    ):
                        summary.skipped_validation += 1
                        if draft_update_context is not None:
                            await _fail_pending_draft_update(
                                session,
                                draft_update_context,
                                reason="detector_source_mismatch",
                                job_id=job_id,
                            )
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
                        LOGGER.info("Skipping stale engagement candidate job_id=%s community_id=%s topic_id=%s source_tg_message_id=%s", job_id, validated_payload.community_id, topic.id, source_message.tg_message_id)
                        if draft_update_context is not None:
                            await _fail_pending_draft_update(
                                session,
                                draft_update_context,
                                reason="rewrite_candidate_stale",
                                job_id=job_id,
                            )
                        continue
                    try:
                        moment_strength = normalize_moment_strength(decision.moment_strength)
                        reply_value = normalize_reply_value(
                            decision.reply_value,
                            has_reply=bool(decision.suggested_reply),
                        )
                    except EngagementValidationError:
                        summary.skipped_validation += 1
                        LOGGER.info("Normalized detector output failed validation job_id=%s community_id=%s topic_id=%s source_tg_message_id=%s", job_id, validated_payload.community_id, topic.id, source_message.tg_message_id)
                        if draft_update_context is not None:
                            await _fail_pending_draft_update(
                                session,
                                draft_update_context,
                                reason="rewrite_candidate_validation_failed",
                                job_id=job_id,
                            )
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
                            source_reply_to_tg_message_id=source_message.reply_to_tg_message_id,
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
                            selected_telegram_account_id=selected_telegram_account_id,
                            ignored_duplicate_candidate_ids=(
                                draft_update_context.ignored_duplicate_candidate_ids
                                if draft_update_context is not None
                                else None
                            ),
                        )
                    except EngagementValidationError:
                        summary.skipped_validation += 1
                        LOGGER.info("Candidate creation validation failed job_id=%s community_id=%s topic_id=%s source_tg_message_id=%s", job_id, validated_payload.community_id, topic.id, source_message.tg_message_id)
                        if draft_update_context is not None:
                            await _fail_pending_draft_update(
                                session,
                                draft_update_context,
                                reason="candidate_creation_validation_failed",
                                job_id=job_id,
                            )
                        continue

                    if creation.created:
                        summary.candidates_created += 1
                        if trigger_candidate.semantic_match is not None:
                            summary.semantic_candidates_created += 1
                    else:
                        summary.skipped_dedupe += 1
                    if draft_update_context is not None:
                        completed_request = await complete_draft_update_request(
                            session,
                            source_candidate_id=draft_update_context.source_candidate.id,
                            replacement_candidate_id=creation.candidate.id,
                        )
                        if completed_request is None:
                            await _fail_pending_draft_update(
                                session,
                                draft_update_context,
                                reason="rewrite_completion_failed",
                                job_id=job_id,
                            )
                        else:
                            LOGGER.info(
                                "Completed pending draft update job_id=%s community_id=%s request_id=%s source_candidate_id=%s replacement_candidate_id=%s created=%s",
                                job_id,
                                validated_payload.community_id,
                                completed_request.id,
                                draft_update_context.source_candidate.id,
                                creation.candidate.id,
                                creation.created,
                            )
                    LOGGER.info("Candidate creation result job_id=%s community_id=%s topic_id=%s source_tg_message_id=%s created=%s semantic_match=%s", job_id, validated_payload.community_id, topic.id, source_message.tg_message_id, creation.created, trigger_candidate.semantic_match is not None)

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
    LOGGER.info("Skipping engagement detect community_id=%s reason=%s", community_id, reason)
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


async def _load_draft_update_context(
    session: AsyncSession,
    *,
    community_id: object,
    request_id: UUID | None,
) -> DraftUpdateExecutionContext | None:
    if request_id is None:
        return None
    request = await get_draft_update_request_by_id(session, request_id=request_id)
    if request is None or request.status != "pending":
        return None
    if request.replacement_candidate_id is not None:
        return None

    source_candidate = await session.get(EngagementCandidate, request.source_candidate_id)
    if source_candidate is None:
        await fail_draft_update_request(session, request_id=request.id)
        return None
    if (
        source_candidate.community_id != community_id
        or source_candidate.status != EngagementCandidateStatus.NEEDS_REVIEW.value
        or source_candidate.topic_id is None
    ):
        await fail_draft_update_request(session, request_id=request.id)
        return None

    topic = await session.get(EngagementTopic, source_candidate.topic_id)
    if topic is None:
        await fail_draft_update_request(session, request_id=request.id)
        return None

    source_text = sanitize_candidate_excerpt(source_candidate.source_excerpt) or ""
    if not source_text:
        await fail_draft_update_request(session, request_id=request.id)
        return None
    revision_requests = await list_draft_update_requests_for_engagement(
        session,
        engagement_id=request.engagement_id,
    )
    ignored_duplicate_candidate_ids = _draft_update_ignored_candidate_ids(
        request=request,
        source_candidate=source_candidate,
        revision_requests=revision_requests,
    )
    return DraftUpdateExecutionContext(
        request=request,
        source_candidate=source_candidate,
        topic=topic,
        source_message=DetectionMessage(
            tg_message_id=source_candidate.source_tg_message_id,
            text=source_text,
            message_date=source_candidate.source_message_date,
            reply_to_tg_message_id=source_candidate.source_reply_to_tg_message_id,
            reply_context=None,
            is_replyable=True,
        ),
        ignored_duplicate_candidate_ids=ignored_duplicate_candidate_ids,
    )


async def _fail_pending_draft_update(
    session: AsyncSession,
    context: DraftUpdateExecutionContext,
    *,
    reason: str,
    job_id: str,
) -> None:
    failed = await fail_draft_update_request(session, request_id=context.request.id)
    if failed is None:
        return
    LOGGER.info(
        "Failed pending draft update job_id=%s community_id=%s request_id=%s source_candidate_id=%s reason=%s",
        job_id,
        context.source_candidate.community_id,
        context.request.id,
        context.source_candidate.id,
        reason,
    )


def _reply_deadline_minutes(runtime_settings: object) -> int:
    value = getattr(runtime_settings, "engagement_reply_deadline_minutes", 90)
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return 90


def _draft_update_ignored_candidate_ids(
    *,
    request: EngagementDraftUpdateRequest,
    source_candidate: EngagementCandidate,
    revision_requests: list[EngagementDraftUpdateRequest],
) -> set[UUID]:
    ignored: set[UUID] = {source_candidate.id}
    for revision_request in revision_requests:
        if revision_request.engagement_id != request.engagement_id:
            continue
        ignored.add(revision_request.source_candidate_id)
        if revision_request.replacement_candidate_id is not None:
            ignored.add(revision_request.replacement_candidate_id)
    return ignored


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
