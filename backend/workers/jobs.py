from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.workers.brief_process import run_brief_process_job
from backend.workers.community_join import run_community_join_job
from backend.workers.community_collect import run_collection_job
from backend.workers.engagement_detect import run_engagement_detect_job
from backend.workers.seed_expand import run_seed_expand_job
from backend.workers.seed_resolve import run_seed_resolve_job
from backend.workers.telegram_entity_resolve import run_telegram_entity_resolve_job


def dispatch_job(job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    set_job_status(job_type, "started")
    handlers = {
        "brief.process": run_brief_process,
        "discovery.run": run_discovery,
        "seed.resolve": run_seed_resolve,
        "seed.expand": run_seed_expand,
        "telegram_entity.resolve": run_telegram_entity_resolve,
        "expansion.run": run_expansion,
        "collection.run": run_collection,
        "analysis.run": run_analysis,
        "community.join": run_community_join,
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
    return run_brief_process_job(payload)


def run_discovery(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "discovery.run", "payload": payload}


def run_seed_resolve(payload: dict[str, Any]) -> dict[str, Any]:
    return run_seed_resolve_job(payload)


def run_seed_expand(payload: dict[str, Any]) -> dict[str, Any]:
    return run_seed_expand_job(payload)


def run_telegram_entity_resolve(payload: dict[str, Any]) -> dict[str, Any]:
    return run_telegram_entity_resolve_job(payload)


def run_expansion(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "expansion.run", "payload": payload}


def run_collection(payload: dict[str, Any]) -> dict[str, Any]:
    return run_collection_job(payload)


def run_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "analysis.run", "payload": payload}


def run_community_join(payload: dict[str, Any]) -> dict[str, Any]:
    return run_community_join_job(payload)


def run_engagement_detect(payload: dict[str, Any]) -> dict[str, Any]:
    return run_engagement_detect_job(payload)


def run_engagement_send(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "engagement.send", "payload": payload}


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
