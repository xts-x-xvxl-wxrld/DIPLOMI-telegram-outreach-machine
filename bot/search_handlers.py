from __future__ import annotations

import re
from typing import Any

from bot.api_client import BotApiError
from bot.formatting import (
    format_api_error,
    format_created_search_run,
    format_job_status,
    format_search_candidate_card,
    format_search_candidate_review,
    format_search_candidates,
    format_search_run_card,
    format_search_run_detail,
    format_search_runs,
    format_search_seed_conversion,
)
from bot.ui import (
    ACTION_SEARCH_CONVERT,
    ACTION_SEARCH_RERANK,
    ACTION_SEARCH_REVIEW,
    ACTION_SEARCH_RUN_CANDIDATES,
    ACTION_SEARCH_RUN_OPEN,
    search_candidate_actions_markup,
    search_candidate_pager_markup,
    search_candidate_review_markup,
    search_run_actions_markup,
    search_run_detail_markup,
    search_seed_conversion_markup,
)
from .runtime_access import _telegram_user_id
from .runtime_context import _api_client
from .runtime_io import _callback_reply, _reply
from .runtime_parsing import _first_arg, _parse_offset

SEARCH_CANDIDATE_PAGE_SIZE = 5
PRIVATE_INVITE_RE = re.compile(r"(?:t\.me|telegram\.me)/(?:\+|joinchat/)", re.IGNORECASE)


async def search_command(update: Any, context: Any) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await _reply(update, "Usage: /search <plain language query>")
        return
    if PRIVATE_INVITE_RE.search(query):
        await _reply(update, "Search only accepts public community topics, not private invite links.")
        return

    client = _api_client(context)
    try:
        data = await client.create_search_run(query, requested_by=_operator_ref(update))
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    run_id = str((data.get("search_run") or {}).get("id", "unknown"))
    await _reply(update, format_created_search_run(data), reply_markup=search_run_actions_markup(run_id))


async def searches_command(update: Any, context: Any) -> None:
    try:
        await _send_search_runs(update, context)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def search_run_command(update: Any, context: Any) -> None:
    search_run_id = _first_arg(context)
    if search_run_id is None:
        await _reply(update, "Usage: /search_run <search_run_id>")
        return
    try:
        await _send_search_run_detail(update, context, search_run_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def search_candidates_command(update: Any, context: Any) -> None:
    search_run_id = _first_arg(context)
    if search_run_id is None:
        await _reply(update, "Usage: /search_candidates <search_run_id>")
        return
    try:
        await _send_search_candidates(update, context, search_run_id, offset=0)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def promote_search_command(update: Any, context: Any) -> None:
    await _review_search_candidate(update, context, action="promote")


async def reject_search_command(update: Any, context: Any) -> None:
    await _review_search_candidate(update, context, action="reject")


async def archive_search_command(update: Any, context: Any) -> None:
    await _review_search_candidate(update, context, action="archive")


async def convert_search_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /convert_search <candidate_id> [seed_group_name]")
        return
    seed_group_name = " ".join(context.args[1:]).strip() or None
    try:
        await _convert_search_candidate(
            update,
            context,
            candidate_id,
            seed_group_name=seed_group_name,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def _send_search_runs(update: Any, context: Any) -> None:
    client = _api_client(context)
    data = await client.list_search_runs(limit=10, offset=0)
    await _callback_reply(update, format_search_runs(data))
    for item in (data.get("items") or [])[:10]:
        run_id = str(item.get("id", "unknown"))
        await _callback_reply(update, format_search_run_card(item), reply_markup=search_run_actions_markup(run_id))


async def _send_search_run_detail(update: Any, context: Any, search_run_id: str) -> None:
    client = _api_client(context)
    detail = await client.get_search_run(search_run_id)
    queries = await client.list_search_run_queries(search_run_id)
    await _callback_reply(
        update,
        format_search_run_detail(detail, queries),
        reply_markup=search_run_detail_markup(search_run_id),
    )


async def _send_search_candidates(
    update: Any,
    context: Any,
    search_run_id: str,
    *,
    offset: int,
) -> None:
    client = _api_client(context)
    data = await client.list_search_candidates(
        search_run_id,
        limit=SEARCH_CANDIDATE_PAGE_SIZE,
        offset=offset,
    )
    await _callback_reply(
        update,
        format_search_candidates(data, offset=offset),
        reply_markup=search_candidate_pager_markup(
            search_run_id,
            offset=offset,
            total=data.get("total", 0),
            page_size=SEARCH_CANDIDATE_PAGE_SIZE,
        ),
    )
    for index, item in enumerate(data.get("items") or [], start=offset + 1):
        candidate_id = str(item.get("id", "unknown"))
        await _callback_reply(
            update,
            format_search_candidate_card(item, index=index),
            reply_markup=search_candidate_actions_markup(candidate_id, status=item.get("status")),
        )


async def _review_search_candidate(update: Any, context: Any, *, action: str) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, f"Usage: /{action}_search <candidate_id>")
        return
    try:
        await _review_search_candidate_id(update, context, candidate_id, action=action)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def _review_search_candidate_id(
    update: Any,
    context: Any,
    candidate_id: str,
    *,
    action: str,
) -> None:
    client = _api_client(context)
    data = await client.review_search_candidate(
        candidate_id,
        action=action,
        requested_by=_operator_ref(update),
    )
    status = (data.get("candidate") or {}).get("status")
    await _callback_reply(
        update,
        format_search_candidate_review(action, data),
        reply_markup=search_candidate_review_markup(candidate_id, status=status),
    )


async def _convert_search_candidate(
    update: Any,
    context: Any,
    candidate_id: str,
    *,
    seed_group_name: str | None = None,
) -> None:
    client = _api_client(context)
    data = await client.convert_search_candidate_to_seed(
        candidate_id,
        seed_group_name=seed_group_name,
        requested_by=_operator_ref(update),
    )
    seed_group_id = (data.get("seed_group") or {}).get("id")
    await _callback_reply(
        update,
        format_search_seed_conversion(data),
        reply_markup=search_seed_conversion_markup(str(seed_group_id) if seed_group_id else None),
    )


async def _start_search_rerank(update: Any, context: Any, search_run_id: str) -> None:
    client = _api_client(context)
    data = await client.start_search_rerank(search_run_id)
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(update, format_job_status(data.get("job") or data), reply_markup=None)
    if job_id != "unknown":
        await _callback_reply(update, f"Check rerank job with /job {job_id}.")


async def _handle_search_callback(update: Any, context: Any, action: str, parts: list[str]) -> bool:
    if action == ACTION_SEARCH_RUN_OPEN and len(parts) == 1:
        await _send_search_run_detail(update, context, parts[0])
        return True
    if action == ACTION_SEARCH_RUN_CANDIDATES and len(parts) == 2:
        await _send_search_candidates(
            update,
            context,
            parts[0],
            offset=_parse_offset(parts[1]),
        )
        return True
    if action == ACTION_SEARCH_REVIEW and len(parts) == 2:
        await _review_search_candidate_id(update, context, parts[0], action=parts[1])
        return True
    if action == ACTION_SEARCH_CONVERT and len(parts) == 1:
        await _convert_search_candidate(update, context, parts[0])
        return True
    if action == ACTION_SEARCH_RERANK and len(parts) == 1:
        await _start_search_rerank(update, context, parts[0])
        return True
    return False


def _operator_ref(update: Any) -> str | None:
    user_id = _telegram_user_id(update)
    if user_id is None:
        return "telegram_bot"
    return f"telegram:{user_id}"


__all__ = [
    "search_command",
    "searches_command",
    "search_run_command",
    "search_candidates_command",
    "promote_search_command",
    "reject_search_command",
    "archive_search_command",
    "convert_search_command",
    "_send_search_runs",
    "_send_search_run_detail",
    "_send_search_candidates",
    "_review_search_candidate_id",
    "_convert_search_candidate",
    "_start_search_rerank",
    "_handle_search_callback",
]
