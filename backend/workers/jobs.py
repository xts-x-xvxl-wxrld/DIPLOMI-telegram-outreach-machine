from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def dispatch_job(job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    set_job_status(job_type, "started")
    handlers = {
        "discovery.run": run_discovery,
        "expansion.run": run_expansion,
        "collection.run": run_collection,
        "analysis.run": run_analysis,
    }
    handler = handlers.get(job_type)
    if handler is None:
        raise ValueError(f"Unknown job type: {job_type}")
    result = handler(payload)
    set_job_status(job_type, "finished")
    return result


def run_discovery(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "discovery.run", "payload": payload}


def run_expansion(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "expansion.run", "payload": payload}


def run_collection(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "collection.run", "payload": payload}


def run_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "stubbed", "job_type": "analysis.run", "payload": payload}


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

