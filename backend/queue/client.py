from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from backend.core.settings import get_settings
from backend.queue.payloads import (
    AnalysisPayload,
    AccountHealthRefreshPayload,
    BriefProcessPayload,
    CommunitySnapshotPayload,
    CollectionPayload,
    CommunityJoinPayload,
    DiscoveryPayload,
    EngagementDetectPayload,
    EngagementSendPayload,
    EngagementTargetResolvePayload,
    ExpansionPayload,
    SearchExpandPayload,
    SearchPlanPayload,
    SearchRankPayload,
    SearchRetrievePayload,
    SeedExpandPayload,
    SeedResolvePayload,
    TelegramEntityResolvePayload,
)
from backend.services.engagement_account_behavior import (
    engagement_send_scheduled_at,
    ensure_aware_utc,
)

WORKER_DISPATCH = "backend.workers.jobs.dispatch_job"
LOGGER = logging.getLogger(__name__)
_INVALID_JOB_ID_CHARS = re.compile(r"[^A-Za-z0-9_-]+")


class QueueUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class QueuedJob:
    id: str
    type: str
    status: str = "queued"


def enqueue_discovery(
    brief_id: UUID,
    *,
    requested_by: str,
    limit: int,
    auto_expand: bool = False,
) -> QueuedJob:
    payload = DiscoveryPayload(
        brief_id=brief_id,
        requested_by=requested_by,
        limit=limit,
        auto_expand=auto_expand,
    )
    return enqueue_job("discovery.run", payload.model_dump(mode="json"), queue_name="default")


def enqueue_brief_process(
    brief_id: UUID,
    *,
    requested_by: str,
    auto_start_discovery: bool = True,
) -> QueuedJob:
    payload = BriefProcessPayload(
        brief_id=brief_id,
        requested_by=requested_by,
        auto_start_discovery=auto_start_discovery,
    )
    return enqueue_job("brief.process", payload.model_dump(mode="json"), queue_name="default")


def enqueue_expansion(
    brief_id: UUID | None,
    community_ids: list[UUID],
    *,
    depth: int,
    requested_by: str,
) -> QueuedJob:
    payload = ExpansionPayload(
        brief_id=brief_id,
        community_ids=community_ids,
        depth=depth,
        requested_by=requested_by,
    )
    return enqueue_job("expansion.run", payload.model_dump(mode="json"), queue_name="default")


def enqueue_seed_resolve(
    seed_group_id: UUID,
    *,
    requested_by: str,
    limit: int = 100,
    retry_failed: bool = False,
) -> QueuedJob:
    payload = SeedResolvePayload(
        seed_group_id=seed_group_id,
        requested_by=requested_by,
        limit=limit,
        retry_failed=retry_failed,
    )
    return enqueue_job("seed.resolve", payload.model_dump(mode="json"), queue_name="default")


def enqueue_seed_expansion(
    seed_group_id: UUID,
    brief_id: UUID | None,
    *,
    depth: int,
    requested_by: str,
) -> QueuedJob:
    payload = SeedExpandPayload(
        seed_group_id=seed_group_id,
        brief_id=brief_id,
        depth=depth,
        requested_by=requested_by,
    )
    return enqueue_job("seed.expand", payload.model_dump(mode="json"), queue_name="default")


def enqueue_telegram_entity_resolve(
    intake_id: UUID,
    *,
    requested_by: str,
) -> QueuedJob:
    payload = TelegramEntityResolvePayload(intake_id=intake_id, requested_by=requested_by)
    return enqueue_job(
        "telegram_entity.resolve",
        payload.model_dump(mode="json"),
        queue_name="default",
    )


def enqueue_search_plan(
    search_run_id: UUID,
    *,
    requested_by: str | None = None,
) -> QueuedJob:
    payload = SearchPlanPayload(search_run_id=search_run_id, requested_by=requested_by)
    return enqueue_job(
        "search.plan",
        payload.model_dump(mode="json"),
        queue_name="default",
        job_id=f"search.plan:{search_run_id}",
    )


def enqueue_search_rank(
    search_run_id: UUID,
    *,
    requested_by: str | None = None,
) -> QueuedJob:
    payload = SearchRankPayload(search_run_id=search_run_id, requested_by=requested_by)
    return enqueue_job(
        "search.rank",
        payload.model_dump(mode="json"),
        queue_name="default",
        job_id=f"search.rank:{search_run_id}",
    )


def enqueue_search_expand(
    search_run_id: UUID,
    *,
    root_search_candidate_ids: list[UUID] | None = None,
    seed_group_ids: list[UUID] | None = None,
    depth: int = 1,
    requested_by: str | None = None,
    max_roots: int = 5,
    max_neighbors_per_root: int = 50,
    max_candidates_per_adapter: int = 50,
) -> QueuedJob:
    payload = SearchExpandPayload(
        search_run_id=search_run_id,
        root_search_candidate_ids=root_search_candidate_ids or [],
        seed_group_ids=seed_group_ids or [],
        depth=depth,
        requested_by=requested_by,
        max_roots=max_roots,
        max_neighbors_per_root=max_neighbors_per_root,
        max_candidates_per_adapter=max_candidates_per_adapter,
    )
    return enqueue_job(
        "search.expand",
        payload.model_dump(mode="json"),
        queue_name="default",
    )


def enqueue_search_retrieve(
    search_run_id: UUID,
    search_query_id: UUID,
    *,
    requested_by: str | None = None,
) -> QueuedJob:
    payload = SearchRetrievePayload(
        search_run_id=search_run_id,
        search_query_id=search_query_id,
        requested_by=requested_by,
    )
    return enqueue_job(
        "search.retrieve",
        payload.model_dump(mode="json"),
        queue_name="default",
        job_id=f"search.retrieve:{search_run_id}:{search_query_id}",
    )


def enqueue_community_snapshot(
    community_id: UUID,
    *,
    reason: str,
    requested_by: str | None = None,
    window_days: int = 90,
) -> QueuedJob:
    payload = CommunitySnapshotPayload(
        community_id=community_id,
        reason=reason,  # type: ignore[arg-type]
        requested_by=requested_by,
        window_days=window_days,
    )
    job_id = f"community.snapshot:{community_id}:{datetime.utcnow():%Y%m%d%H}"
    return enqueue_job(
        "community.snapshot",
        payload.model_dump(mode="json"),
        queue_name="high",
        job_id=job_id,
    )


def enqueue_collection(
    community_id: UUID,
    *,
    reason: str,
    requested_by: str | None = None,
    window_days: int = 90,
    now: datetime | None = None,
) -> QueuedJob:
    payload = CollectionPayload(
        community_id=community_id,
        reason=reason,  # type: ignore[arg-type]
        requested_by=requested_by,
        window_days=window_days,
    )
    queue_name = "high" if reason == "manual" else "scheduled"
    job_id = _collection_job_id(community_id, reason=reason, now=now)
    return enqueue_job(
        "collection.run",
        payload.model_dump(mode="json"),
        queue_name=queue_name,
        job_id=job_id,
    )


def enqueue_analysis(collection_run_id: UUID, *, requested_by: str | None = None) -> QueuedJob:
    payload = AnalysisPayload(collection_run_id=collection_run_id, requested_by=requested_by)
    return enqueue_job(
        "analysis.run",
        payload.model_dump(mode="json"),
        queue_name="analysis",
        job_id=f"analysis:{collection_run_id}",
    )


def enqueue_community_join(
    community_id: UUID,
    *,
    requested_by: str,
    telegram_account_id: UUID | None = None,
) -> QueuedJob:
    payload = CommunityJoinPayload(
        community_id=community_id,
        telegram_account_id=telegram_account_id,
        requested_by=requested_by,
    )
    return enqueue_job("community.join", payload.model_dump(mode="json"), queue_name="default")


def enqueue_engagement_target_resolve(
    target_id: UUID,
    *,
    requested_by: str,
) -> QueuedJob:
    payload = EngagementTargetResolvePayload(target_id=target_id, requested_by=requested_by)
    return enqueue_job(
        "engagement_target.resolve",
        payload.model_dump(mode="json"),
        queue_name="engagement",
        job_id=f"engagement_target.resolve:{target_id}",
    )


def enqueue_engagement_detect(
    community_id: UUID,
    *,
    collection_run_id: UUID | None = None,
    window_minutes: int = 60,
    requested_by: str | None = None,
    job_id_prefix: str = "engagement.detect",
    now: datetime | None = None,
) -> QueuedJob:
    payload = EngagementDetectPayload(
        community_id=community_id,
        collection_run_id=collection_run_id,
        window_minutes=window_minutes,
        requested_by=requested_by,
    )
    job_id = (
        f"{job_id_prefix}:{community_id}:{collection_run_id}"
        if collection_run_id is not None
        else _hourly_job_id(job_id_prefix, community_id, now=now)
    )
    return enqueue_job(
        "engagement.detect",
        payload.model_dump(mode="json"),
        queue_name="engagement",
        job_id=job_id,
    )


def enqueue_manual_engagement_detect(
    community_id: UUID,
    *,
    window_minutes: int = 60,
    requested_by: str,
    now: datetime | None = None,
) -> QueuedJob:
    return enqueue_engagement_detect(
        community_id,
        window_minutes=window_minutes,
        requested_by=requested_by,
        job_id_prefix="engagement.detect.manual",
        now=now,
    )


def enqueue_engagement_send(
    candidate_id: UUID,
    *,
    approved_by: str,
    scheduled_at: datetime | None = None,
    delay_seconds: int | None = None,
    now: datetime | None = None,
) -> QueuedJob:
    payload = EngagementSendPayload(candidate_id=candidate_id, approved_by=approved_by)
    send_at = _engagement_send_scheduled_at(
        candidate_id,
        scheduled_at=scheduled_at,
        delay_seconds=delay_seconds,
        now=now,
    )
    return enqueue_job(
        "engagement.send",
        payload.model_dump(mode="json"),
        queue_name="engagement",
        job_id=f"engagement.send:{candidate_id}",
        scheduled_at=send_at,
    )


def enqueue_account_health_refresh(
    *,
    account_ids: list[UUID] | None = None,
    spot_check_limit: int = 2,
    now: datetime | None = None,
) -> QueuedJob:
    payload = AccountHealthRefreshPayload(
        account_ids=account_ids or [],
        spot_check_limit=spot_check_limit,
    )
    return enqueue_job(
        "account.health_refresh",
        payload.model_dump(mode="json"),
        queue_name="default",
        job_id=_account_health_refresh_job_id(now=now),
    )


def enqueue_job(
    job_type: str,
    payload: dict[str, Any],
    *,
    queue_name: str,
    job_id: str | None = None,
    scheduled_at: datetime | None = None,
) -> QueuedJob:
    Queue, Retry, redis_conn = _queue_dependencies()
    normalized_job_id = _normalize_job_id(job_id)
    due_at = None if scheduled_at is None else ensure_aware_utc(scheduled_at)
    try:
        queue = Queue(queue_name, connection=redis_conn)
        enqueue_kwargs = _enqueue_kwargs(
            job_type=job_type,
            payload=payload,
            job_id=normalized_job_id,
            Retry=Retry,
            scheduled_at=due_at,
        )
        if due_at is None:
            job = queue.enqueue(WORKER_DISPATCH, job_type, payload, **enqueue_kwargs)
        else:
            job = queue.enqueue_at(due_at, WORKER_DISPATCH, job_type, payload, **enqueue_kwargs)
    except Exception as exc:
        if normalized_job_id is not None and _is_duplicate_job_error(exc):
            return QueuedJob(id=normalized_job_id, type=job_type, status="duplicate")
        LOGGER.exception(
            "Failed to enqueue job",
            extra={"job_type": job_type, "queue_name": queue_name, "job_id": normalized_job_id},
        )
        raise QueueUnavailable("Queue backend unavailable") from exc
    return QueuedJob(id=job.id, type=job_type, status="scheduled" if due_at is not None else "queued")


def fetch_job_status(job_id: str, *, redis_url: str | None = None) -> dict[str, Any] | None:
    _Queue, _Retry, redis_conn = _queue_dependencies(redis_url)
    try:
        from rq.job import Job
    except ImportError as exc:
        raise QueueUnavailable("RQ is not installed") from exc

    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        return None

    return {
        "id": job.id,
        "type": job.meta.get("job_type"),
        "status": job.get_status(refresh=True),
        "meta": job.meta or {},
        "error": job.exc_info,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "ended_at": job.ended_at,
    }


def ping_redis(redis_url: str | None = None) -> None:
    try:
        from redis import Redis
    except ImportError as exc:
        raise QueueUnavailable("redis is not installed") from exc

    try:
        Redis.from_url(redis_url or get_settings().redis_url).ping()
    except Exception as exc:
        raise QueueUnavailable("Queue backend unavailable") from exc


def _queue_dependencies(redis_url: str | None = None):
    try:
        from redis import Redis
        from rq import Queue, Retry
    except ImportError as exc:
        raise QueueUnavailable("redis and rq must be installed before queue operations run") from exc

    redis_conn = Redis.from_url(redis_url or get_settings().redis_url)
    return Queue, Retry, redis_conn


def _retry_for(job_type: str, Retry):
    if job_type == "brief.process":
        return Retry(max=3, interval=[60, 300, 900])
    if job_type == "discovery.run":
        return Retry(max=3, interval=[60, 300, 900])
    if job_type in {"seed.resolve", "seed.expand", "telegram_entity.resolve"}:
        return Retry(max=3, interval=[300, 900, 3600])
    if job_type in {"search.plan", "search.rank", "search.expand"}:
        return Retry(max=2, interval=[60, 300])
    if job_type == "expansion.run":
        return Retry(max=3, interval=[300, 900, 3600])
    if job_type == "collection.run":
        return Retry(max=2, interval=[600, 1800])
    if job_type == "analysis.run":
        return Retry(max=3, interval=[60, 300, 1800])
    if job_type == "community.join":
        return Retry(max=2, interval=[600, 3600])
    if job_type == "engagement_target.resolve":
        return Retry(max=3, interval=[300, 900, 3600])
    if job_type == "engagement.detect":
        return Retry(max=2, interval=[300, 900])
    if job_type == "engagement.send":
        return Retry(max=1, interval=[600])
    if job_type == "account.health_refresh":
        return Retry(max=1, interval=[1800])
    return Retry(max=1, interval=[60])


def _enqueue_kwargs(
    *,
    job_type: str,
    payload: dict[str, Any],
    job_id: str | None,
    Retry,
    scheduled_at: datetime | None,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "retry": _retry_for(job_type, Retry),
        "result_ttl": 86400,
        "failure_ttl": 604800,
        "meta": _job_meta(job_type=job_type, payload=payload, scheduled_at=scheduled_at),
    }


def _job_meta(
    *,
    job_type: str,
    payload: dict[str, Any],
    scheduled_at: datetime | None,
) -> dict[str, Any]:
    status_message = "scheduled" if scheduled_at is not None else "queued"
    meta = {"job_type": job_type, "status_message": status_message, **payload}
    if scheduled_at is not None:
        meta["scheduled_at"] = scheduled_at.isoformat()
    return meta


def _engagement_send_scheduled_at(
    candidate_id: UUID,
    *,
    scheduled_at: datetime | None,
    delay_seconds: int | None,
    now: datetime | None,
) -> datetime:
    if scheduled_at is not None and delay_seconds is not None:
        raise ValueError("scheduled_at and delay_seconds cannot both be provided")
    current_time = ensure_aware_utc(now or datetime.now(timezone.utc))
    if scheduled_at is not None:
        return ensure_aware_utc(scheduled_at)
    if delay_seconds is not None:
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be non-negative")
        return current_time + timedelta(seconds=delay_seconds)
    return engagement_send_scheduled_at(candidate_id, now=current_time)


def _hourly_job_id(prefix: str, community_id: UUID, *, now: datetime | None = None) -> str:
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is not None:
        current_time = current_time.astimezone(timezone.utc)
    return f"{prefix}:{community_id}:{current_time:%Y%m%d%H}"


def _collection_job_id(community_id: UUID, *, reason: str, now: datetime | None = None) -> str:
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is not None:
        current_time = current_time.astimezone(timezone.utc)
    if reason == "engagement":
        return f"collection:engagement:{community_id}:{current_time:%Y%m%d%H%M}"
    return f"collection:{community_id}:{current_time:%Y%m%d%H}"


def _account_health_refresh_job_id(*, now: datetime | None = None) -> str:
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is not None:
        current_time = current_time.astimezone(timezone.utc)
    bucket_hour = current_time.hour - (current_time.hour % 8)
    bucketed_time = current_time.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)
    return f"account.health_refresh:{bucketed_time:%Y%m%d%H}"


def _is_duplicate_job_error(exc: Exception) -> bool:
    if exc.__class__.__name__ == "DuplicateJobError":
        return True
    message = str(exc).casefold()
    return "job" in message and "already exist" in message


def _normalize_job_id(job_id: str | None) -> str | None:
    if job_id is None:
        return None
    normalized = _INVALID_JOB_ID_CHARS.sub("_", job_id).strip("_")
    return normalized or None
