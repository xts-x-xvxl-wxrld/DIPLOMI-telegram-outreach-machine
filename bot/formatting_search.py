from __future__ import annotations

from decimal import Decimal
from typing import Any

from .formatting_common import _action_block, _bullet, _field, _headline, _section, _shorten, _status_icon


def format_created_search_run(data: dict[str, Any]) -> str:
    search_run = data.get("search_run") or {}
    job = data.get("job") or {}
    run_id = search_run.get("id", "unknown")
    job_id = job.get("id", "unknown")
    return "\n".join(
        [
            _headline("Community search queued."),
            _field("Search", search_run.get("normalized_title") or search_run.get("raw_query", "unknown")),
            _field("Run ID", run_id),
            _field("Planning job", f"{job_id} ({job.get('type', 'search.plan')})"),
            *_action_block([f"Open: /search_run {run_id}", f"Candidates: /search_candidates {run_id}"]),
        ]
    )


def format_search_runs(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return _headline("No community searches yet. Start one with /search <query>.")
    return "\n".join(
        [
            _headline(f"Community searches ({total})"),
            _bullet("Open a run card below or use /search_run <search_run_id>."),
        ]
    )


def format_search_run_card(item: dict[str, Any]) -> str:
    run_id = item.get("id", "unknown")
    lines = [
        _headline(item.get("normalized_title") or item.get("raw_query") or "Search run"),
        _field("Status", item.get("status", "unknown"), icon=_status_icon(item.get("status"))),
        _field("Queries", item.get("query_count", 0)),
        _field("Candidates", item.get("candidate_count", 0)),
        _field("Promoted", item.get("promoted_count", 0)),
        _field("Rejected", item.get("rejected_count", 0)),
    ]
    if item.get("last_error"):
        lines.append(_field("Latest error", _shorten(str(item["last_error"]), 240)))
    lines.append(_field("Run ID", run_id))
    return "\n".join(lines)


def format_search_run_detail(detail: dict[str, Any], queries: dict[str, Any] | None = None) -> str:
    search_run = detail.get("search_run") or {}
    counts = detail.get("counts") or {}
    query_items = (queries or {}).get("items") or []
    query_statuses: dict[str, int] = {}
    for item in query_items:
        status = str(item.get("status", "unknown"))
        query_statuses[status] = query_statuses.get(status, 0) + 1

    lines = [
        _headline(search_run.get("normalized_title") or search_run.get("raw_query") or "Search run"),
        _field("Status", search_run.get("status", "unknown"), icon=_status_icon(search_run.get("status"))),
        _field("Queries", f"{counts.get('queries_completed', 0)}/{counts.get('queries', 0)} completed"),
        _field("Candidates", counts.get("candidates", 0)),
        _field("Promoted", counts.get("promoted", 0)),
        _field("Rejected", counts.get("rejected", 0)),
        _field("Archived", counts.get("archived", 0)),
    ]
    if search_run.get("ranking_version"):
        lines.append(_field("Ranking", search_run["ranking_version"]))
    if query_statuses:
        lines.append(_field("Query statuses", ", ".join(f"{key}={value}" for key, value in sorted(query_statuses.items()))))
    if search_run.get("last_error"):
        lines.append(_field("Latest error", _shorten(str(search_run["last_error"]), 400)))
    lines.extend(
        [
            "",
            _field("Run ID", search_run.get("id", "unknown")),
            *_action_block([f"Candidates: /search_candidates {search_run.get('id', 'unknown')}"]),
        ]
    )
    return "\n".join(lines)


def format_search_candidates(data: dict[str, Any], *, offset: int = 0) -> str:
    items = data.get("items") or []
    total = data.get("total", len(items))
    if not items:
        return _headline("No search candidate communities on this page.")
    return _headline(f"Search candidates ({offset + 1}-{offset + len(items)} of {total})")


def format_search_candidate_card(item: dict[str, Any], *, index: int | None = None) -> str:
    title = item.get("title") or item.get("username") or item.get("telegram_url") or "Untitled community"
    heading = f"{index}. {title}" if index is not None else str(title)
    score = _format_score(item.get("score"))
    lines = [
        _headline(heading),
        _field("Status", item.get("status", "unknown"), icon=_status_icon(item.get("status"))),
    ]
    if item.get("username"):
        lines.append(_field("Username", f"@{item['username']}"))
    if item.get("telegram_url"):
        lines.append(_field("Link", item["telegram_url"]))
    if item.get("member_count") is not None:
        lines.append(_field("Members", item["member_count"]))
    if score is not None:
        lines.append(_field("Score", score))
    component_summary = _score_components_summary(item.get("score_components") or {})
    if component_summary:
        lines.append(_field("Score reasons", component_summary))

    evidence = item.get("evidence_summary") or {}
    evidence_bits = []
    if evidence.get("total") is not None:
        evidence_bits.append(f"{evidence.get('total')} facts")
    if evidence.get("types"):
        evidence_bits.append(", ".join(str(value) for value in evidence["types"][:4]))
    if evidence_bits:
        lines.append(_bullet("Evidence: " + " | ".join(evidence_bits)))
    for snippet in (evidence.get("snippets") or [])[:2]:
        lines.append(_bullet(_shorten(str(snippet), 180)))
    if item.get("description"):
        lines.extend(["", _section("Description"), _bullet(_shorten(str(item["description"]), 240))])
    lines.extend(["", _field("Candidate ID", item.get("id", "unknown"))])
    if item.get("community_id"):
        lines.append(_field("Community ID", item["community_id"]))
    return "\n".join(lines)


def format_search_candidate_review(action: str, data: dict[str, Any]) -> str:
    candidate = data.get("candidate") or {}
    return "\n".join(
        [
            _headline("Search candidate reviewed."),
            _field("Action", action),
            _field("Status", candidate.get("status", "unknown"), icon=_status_icon(candidate.get("status"))),
            _field("Candidate ID", candidate.get("id", "unknown")),
        ]
    )


def format_search_seed_conversion(data: dict[str, Any]) -> str:
    seed_group = data.get("seed_group") or {}
    seed_channel = data.get("seed_channel") or {}
    candidate = data.get("candidate") or {}
    return "\n".join(
        [
            _headline("Search candidate converted to seed."),
            _field("Seed group", seed_group.get("name", "unknown")),
            _field("Seed channel", seed_channel.get("telegram_url") or seed_channel.get("raw_value", "unknown")),
            _field("Seed status", seed_channel.get("status", "unknown")),
            _field("Candidate status", candidate.get("status", "unknown"), icon=_status_icon(candidate.get("status"))),
            *_action_block([f"Open seed group: /seed {seed_group.get('id', 'unknown')}"]),
        ]
    )


def _format_score(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{Decimal(str(value)):.1f}"
    except Exception:
        return str(value)


def _score_components_summary(components: dict[str, Any]) -> str:
    parts = []
    for key, value in sorted(components.items(), key=lambda item: str(item[0]))[:4]:
        parts.append(f"{key}={value}")
    return ", ".join(parts)
