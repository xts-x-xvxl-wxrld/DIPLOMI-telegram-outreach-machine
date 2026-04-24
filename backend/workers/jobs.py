from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def dispatch_job(job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    set_job_status(job_type, "started")
    handlers = {
        "brief.process": run_brief_process,
        "discovery.run": run_discovery,
        "seed.resolve": run_seed_resolve,
        "seed.expand": run_seed_expand,
        "telegram_entity.resolve": run_telegram_entity_resolve,
        "search.plan": run_search_plan,
        "search.retrieve": run_search_retrieve,
        "search.rank": run_search_rank,
        "search.expand": run_search_expand,
        "expansion.run": run_expansion,
        "community.snapshot": run_community_snapshot,
        "collection.run": run_collection,
        "analysis.run": run_analysis,
        "community.join": run_community_join,
        "engagement_target.resolve": run_engagement_target_resolve,
        "engagement.detect": run_engagement_detect,
        "engagement.send": run_engagement_send,
    }
    handler = handlers.get(job_type)
    if handler is None:
        raise ValueError(f"Unknown job type: {job_type}")
    result = handler(payload)
    set_job_status(job_type, "finished")
    return result


def run_brief_process(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.brief_process import run_brief_process_job

    return run_brief_process_job(payload)


def run_discovery(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "discovery.run", "payload": payload}


def run_seed_resolve(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.seed_resolve import run_seed_resolve_job

    return run_seed_resolve_job(payload)


def run_seed_expand(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.seed_expand import run_seed_expand_job

    return run_seed_expand_job(payload)


def run_telegram_entity_resolve(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.telegram_entity_resolve import run_telegram_entity_resolve_job

    return run_telegram_entity_resolve_job(payload)


def run_search_plan(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.search_plan import run_search_plan_job

    return run_search_plan_job(payload)


def run_search_retrieve(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.search_retrieve import run_search_retrieve_job

    return run_search_retrieve_job(payload)


def run_search_rank(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.search_rank import run_search_rank_job

    return run_search_rank_job(payload)


def run_search_expand(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.search_expand import run_search_expand_job

    return run_search_expand_job(payload)


def run_expansion(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "expansion.run", "payload": payload}


def run_community_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.community_snapshot import run_community_snapshot_job

    return run_community_snapshot_job(payload)


def run_collection(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.collection import run_collection_job

    return run_collection_job(payload)


def run_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "analysis.run", "payload": payload}


def run_community_join(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.community_join import run_community_join_job

    return run_community_join_job(payload)


def run_engagement_target_resolve(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.engagement_target_resolve import run_engagement_target_resolve_job

    return run_engagement_target_resolve_job(payload)


def run_engagement_detect(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.engagement_detect import run_engagement_detect_job

    return run_engagement_detect_job(payload)


def run_engagement_send(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.workers.engagement_send import run_engagement_send_job

    return run_engagement_send_job(payload)


def set_job_status(job_type: str, status_message: str) -> None:
    try:
        from rq import get_current_job
    except ImportError:
        return

    job = get_current_job()
    if job is None:
        return
    now = datetime.now(timezone.utc).isoformat()
    job.meta.update(
        {
            "job_type": job_type,
            "last_heartbeat_at": now,
            "status_message": status_message,
        }
    )
    job.save_meta()
