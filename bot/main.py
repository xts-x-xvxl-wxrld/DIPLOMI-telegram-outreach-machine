from __future__ import annotations

import csv
import io
from typing import Any

from bot.api_client import BotApiClient, BotApiError
from bot.config import BotSettings, load_settings, validate_runtime_settings
from bot.formatting import (
    format_access_denied,
    format_accounts,
    format_api_error,
    format_briefs_unavailable,
    format_candidate_card,
    format_candidates,
    format_collection_job,
    format_community_detail,
    format_created_brief,
    format_engagement_candidate_card,
    format_engagement_candidate_review,
    format_engagement_candidates,
    format_engagement_home,
    format_engagement_job_response,
    format_engagement_topic_card,
    format_engagement_topics,
    format_job_status,
    format_member_export,
    format_members,
    format_review,
    format_seed_channels,
    format_seed_group,
    format_seed_group_card,
    format_seed_group_resolution,
    format_seed_groups,
    format_seed_import,
    format_start,
    format_telegram_entity_intake,
    format_telegram_entity_submission,
    format_whoami,
)
from bot.ui import (
    ACCOUNTS_MENU_LABEL,
    ACTION_APPROVE_COMMUNITY,
    ACTION_COLLECT_COMMUNITY,
    ACTION_COMMUNITY_MEMBERS,
    ACTION_ENGAGEMENT_APPROVE,
    ACTION_ENGAGEMENT_CANDIDATES,
    ACTION_ENGAGEMENT_HOME,
    ACTION_ENGAGEMENT_REJECT,
    ACTION_ENGAGEMENT_SEND,
    ACTION_ENGAGEMENT_TOPIC_LIST,
    ACTION_ENGAGEMENT_TOPIC_TOGGLE,
    ACTION_JOB_STATUS,
    ACTION_OPEN_COMMUNITY,
    ACTION_OPEN_SEED_GROUP,
    ACTION_REJECT_COMMUNITY,
    ACTION_RESOLVE_SEED_GROUP,
    ACTION_SEED_CANDIDATES,
    ACTION_SEED_CHANNELS,
    HELP_MENU_LABEL,
    ENGAGEMENT_MENU_LABEL,
    SEEDS_MENU_LABEL,
    candidate_actions_markup,
    community_actions_markup,
    engagement_candidate_actions_markup,
    engagement_candidate_filter_markup,
    engagement_candidate_pager_markup,
    engagement_candidate_send_markup,
    engagement_home_markup,
    engagement_job_markup,
    engagement_topic_actions_markup,
    engagement_topic_pager_markup,
    job_actions_markup,
    main_menu_markup,
    member_pager_markup,
    parse_callback_data,
    review_result_markup,
    seed_group_actions_markup,
    seed_group_pager_markup,
)


API_CLIENT_KEY = "api_client"
CANDIDATE_PAGE_SIZE = 5
CHANNEL_PAGE_SIZE = 5
MEMBER_PAGE_SIZE = 10
MEMBER_EXPORT_PAGE_SIZE = 1000
ENGAGEMENT_CANDIDATE_PAGE_SIZE = 5
ENGAGEMENT_TOPIC_PAGE_SIZE = 5
ENGAGEMENT_CANDIDATE_STATUSES = {"needs_review", "approved", "failed", "sent", "rejected"}


async def start_command(update: Any, context: Any) -> None:
    await _reply(update, format_start(), reply_markup=main_menu_markup())


async def help_command(update: Any, context: Any) -> None:
    await _reply(update, format_start(), reply_markup=main_menu_markup())


async def whoami_command(update: Any, context: Any) -> None:
    user = _telegram_user(update)
    user_id = _telegram_user_id(update)
    if user_id is None:
        await _reply(update, "Telegram did not include a user ID on this update.")
        return

    await _reply(update, format_whoami(user_id, username=_telegram_username(user)))


async def briefs_command(update: Any, context: Any) -> None:
    await _reply(update, format_briefs_unavailable(), reply_markup=main_menu_markup())


async def brief_command(update: Any, context: Any) -> None:
    raw_input = " ".join(context.args).strip()
    if not raw_input:
        await _reply(update, "Usage: /brief <audience description>")
        return

    client = _api_client(context)
    try:
        data = await client.create_brief(raw_input)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    await _reply(update, format_created_brief(data))


async def job_command(update: Any, context: Any) -> None:
    job_id = _first_arg(context)
    if job_id is None:
        await _reply(update, "Usage: /job <job_id>")
        return

    await _send_job_status(update, context, job_id)


async def entity_command(update: Any, context: Any) -> None:
    intake_id = _first_arg(context)
    if intake_id is None:
        await _reply(update, "Usage: /entity <intake_id>")
        return

    client = _api_client(context)
    try:
        data = await client.get_telegram_entity(intake_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    await _reply(update, format_telegram_entity_intake(data))


async def candidates_command(update: Any, context: Any) -> None:
    seed_group_id = _first_arg(context)
    if seed_group_id is None:
        await _reply(update, "Usage: /candidates <seed_group_id>")
        return

    await _send_seed_group_candidates(update, context, seed_group_id, offset=0)


async def approve_command(update: Any, context: Any) -> None:
    await _review(update, context, decision="approve")


async def reject_command(update: Any, context: Any) -> None:
    await _review(update, context, decision="reject")


async def accounts_command(update: Any, context: Any) -> None:
    client = _api_client(context)
    try:
        data = await client.get_accounts()
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    await _reply(update, format_accounts(data), reply_markup=main_menu_markup())


async def seeds_command(update: Any, context: Any) -> None:
    client = _api_client(context)
    try:
        data = await client.list_seed_groups()
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    await _reply(update, format_seed_groups(data), reply_markup=main_menu_markup())
    for group in (data.get("items") or [])[:10]:
        await _reply(
            update,
            format_seed_group_card(group),
            reply_markup=seed_group_actions_markup(str(group.get("id", "unknown"))),
        )
    remaining = max((data.get("total", 0) or 0) - 10, 0)
    if remaining:
        await _reply(update, f"...and {remaining} more seed groups. Open one with /seed <seed_group_id>.")


async def seed_command(update: Any, context: Any) -> None:
    seed_group_id = _first_arg(context)
    if seed_group_id is None:
        await _reply(update, "Usage: /seed <seed_group_id>")
        return

    await _send_seed_group_detail(update, context, seed_group_id)


async def channels_command(update: Any, context: Any) -> None:
    seed_group_id = _first_arg(context)
    if seed_group_id is None:
        await _reply(update, "Usage: /channels <seed_group_id>")
        return

    await _send_seed_group_channels(update, context, seed_group_id, offset=0)


async def resolveseeds_command(update: Any, context: Any) -> None:
    seed_group_id = _first_arg(context)
    if seed_group_id is None:
        await _reply(update, "Usage: /resolveseeds <seed_group_id>")
        return

    await _start_seed_group_resolution(update, context, seed_group_id)


async def community_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /community <community_id>")
        return

    await _send_community_detail(update, context, community_id)


async def collect_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /collect <community_id>")
        return

    await _start_collection(update, context, community_id)


async def members_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /members <community_id>")
        return

    await _send_community_members(update, context, community_id, offset=_second_arg_as_offset(context))


async def exportmembers_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /exportmembers <community_id>")
        return

    client = _api_client(context)
    try:
        detail = await client.get_community(community_id)
        export_data = await _fetch_all_community_members(client, community_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    community = detail.get("community") or {}
    title = community.get("title") or community.get("username") or community_id
    csv_bytes = _members_csv_bytes(export_data.get("items") or [])
    file_name = f"community-{community_id}-members.csv"
    await _reply_document(
        update,
        document_bytes=csv_bytes,
        file_name=file_name,
        caption=format_member_export(export_data, community_title=title),
    )


async def engagement_candidates_command(update: Any, context: Any) -> None:
    status = _engagement_candidate_status_arg(context)
    try:
        await _send_engagement_candidates(update, context, status=status, offset=0)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_command(update: Any, context: Any) -> None:
    try:
        await _send_engagement_home(update, context)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_topics_command(update: Any, context: Any) -> None:
    try:
        await _send_engagement_topics(update, context, offset=0)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def create_engagement_topic_command(update: Any, context: Any) -> None:
    parsed = _parse_create_engagement_topic_args(context)
    if parsed is None:
        await _reply(update, _create_engagement_topic_usage())
        return

    name, guidance, keywords = parsed
    client = _api_client(context)
    try:
        data = await client.create_engagement_topic(
            name=name,
            stance_guidance=guidance,
            trigger_keywords=keywords,
            active=True,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    topic_id = str(data.get("id", "unknown"))
    await _reply(
        update,
        "Engagement topic created.\n\n" + format_engagement_topic_card(data),
        reply_markup=engagement_topic_actions_markup(topic_id, active=bool(data.get("active"))),
    )


async def toggle_engagement_topic_command(update: Any, context: Any) -> None:
    if len(context.args) < 2:
        await _reply(update, "Usage: /toggle_engagement_topic <topic_id> <on|off>")
        return

    topic_id = str(context.args[0]).strip()
    active = _parse_on_off(str(context.args[1]))
    if not topic_id or active is None:
        await _reply(update, "Usage: /toggle_engagement_topic <topic_id> <on|off>")
        return

    try:
        await _toggle_engagement_topic(update, context, topic_id, active=active)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def approve_reply_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /approve_reply <candidate_id>")
        return

    try:
        await _review_engagement_candidate(
            update,
            context,
            candidate_id,
            action="approve",
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def reject_reply_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /reject_reply <candidate_id>")
        return

    try:
        await _review_engagement_candidate(
            update,
            context,
            candidate_id,
            action="reject",
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def send_reply_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /send_reply <candidate_id>")
        return

    try:
        await _send_engagement_reply(update, context, candidate_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def seed_csv_document(update: Any, context: Any) -> None:
    if update.message is None or update.message.document is None:
        return

    document = update.message.document
    file_name = document.file_name or "seeds.csv"
    if not file_name.lower().endswith(".csv"):
        await _reply(update, "Please upload a .csv file with group_name,channel columns.")
        return

    try:
        telegram_file = await document.get_file()
        data = await telegram_file.download_as_bytearray()
        csv_text = bytes(data).decode("utf-8-sig")
    except UnicodeDecodeError:
        await _reply(update, "Could not read the CSV. Please upload UTF-8 text.")
        return

    client = _api_client(context)
    try:
        response = await client.import_seed_csv(csv_text, file_name=file_name)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    await _reply(update, format_seed_import(response), reply_markup=main_menu_markup())
    for group in (response.get("groups") or [])[:5]:
        await _reply(
            update,
            format_seed_group_card(group),
            reply_markup=seed_group_actions_markup(str(group.get("id", "unknown"))),
        )


async def telegram_entity_text(update: Any, context: Any) -> None:
    if update.message is None or update.message.text is None:
        return

    raw_text = update.message.text.strip()
    if not _looks_like_telegram_reference(raw_text):
        return

    client = _api_client(context)
    try:
        response = await client.submit_telegram_entity(raw_text)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    job_id = str((response.get("job") or {}).get("id", "unknown"))
    await _reply(
        update,
        format_telegram_entity_submission(response),
        reply_markup=job_actions_markup(job_id),
    )


async def callback_query(update: Any, context: Any) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return

    await query.answer()
    action, parts = parse_callback_data(query.data)

    try:
        if action == ACTION_OPEN_SEED_GROUP and len(parts) == 1:
            await _send_seed_group_detail(update, context, parts[0])
            return
        if action == ACTION_RESOLVE_SEED_GROUP and len(parts) == 1:
            await _start_seed_group_resolution(update, context, parts[0])
            return
        if action == ACTION_SEED_CHANNELS and len(parts) == 2:
            await _send_seed_group_channels(
                update,
                context,
                parts[0],
                offset=_parse_offset(parts[1]),
            )
            return
        if action == ACTION_SEED_CANDIDATES and len(parts) == 2:
            await _send_seed_group_candidates(
                update,
                context,
                parts[0],
                offset=_parse_offset(parts[1]),
            )
            return
        if action == ACTION_OPEN_COMMUNITY and len(parts) == 1:
            await _send_community_detail(update, context, parts[0])
            return
        if action == ACTION_COLLECT_COMMUNITY and len(parts) == 1:
            await _start_collection(update, context, parts[0])
            return
        if action == ACTION_COMMUNITY_MEMBERS and len(parts) == 2:
            await _send_community_members(
                update,
                context,
                parts[0],
                offset=_parse_offset(parts[1]),
            )
            return
        if action == ACTION_JOB_STATUS and len(parts) == 1:
            await _send_job_status(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_HOME:
            await _send_engagement_home(update, context)
            return
        if action == ACTION_ENGAGEMENT_CANDIDATES and parts:
            status, offset = _engagement_callback_status_and_offset(parts)
            await _send_engagement_candidates(update, context, status=status, offset=offset)
            return
        if action == ACTION_ENGAGEMENT_TOPIC_LIST and parts:
            await _send_engagement_topics(update, context, offset=_parse_offset(parts[0]))
            return
        if action == ACTION_ENGAGEMENT_TOPIC_TOGGLE and len(parts) == 2:
            await _toggle_engagement_topic(
                update,
                context,
                parts[0],
                active=parts[1] == "1",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_APPROVE and len(parts) == 1:
            await _review_engagement_candidate(
                update,
                context,
                parts[0],
                action="approve",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_REJECT and len(parts) == 1:
            await _review_engagement_candidate(
                update,
                context,
                parts[0],
                action="reject",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_SEND and len(parts) == 1:
            await _send_engagement_reply(update, context, parts[0])
            return
        if action in {ACTION_APPROVE_COMMUNITY, ACTION_REJECT_COMMUNITY} and len(parts) == 1:
            decision = "approve" if action == ACTION_APPROVE_COMMUNITY else "reject"
            await _review_callback(update, context, parts[0], decision=decision)
            return
    except BotApiError as exc:
        await _callback_reply(update, format_api_error(exc.message))
        return

    await _callback_reply(update, "That action is no longer available. Try /seeds or /community.")


async def access_gate(update: Any, context: Any) -> None:
    settings: BotSettings = context.application.bot_data["settings"]
    if _is_identity_command(update) or _is_authorized_update(update, settings):
        return

    await _deny_access(update)
    from telegram.ext import ApplicationHandlerStop

    raise ApplicationHandlerStop


async def _review(update: Any, context: Any, *, decision: str) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, f"Usage: /{decision} <community_id>")
        return

    client = _api_client(context)
    try:
        data = await client.review_community(community_id, decision=decision)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    job = data.get("job") or {}
    await _reply(
        update,
        format_review(decision, data),
        reply_markup=review_result_markup(
            str((data.get("community") or {}).get("id", community_id)),
            str(job.get("id")) if job.get("id") else None,
        ),
    )


async def _review_callback(update: Any, context: Any, community_id: str, *, decision: str) -> None:
    client = _api_client(context)
    data = await client.review_community(community_id, decision=decision)
    job = data.get("job") or {}
    await _edit_callback_message(
        update,
        format_review(decision, data),
        reply_markup=review_result_markup(
            str((data.get("community") or {}).get("id", community_id)),
            str(job.get("id")) if job.get("id") else None,
        ),
    )


async def _send_seed_group_detail(update: Any, context: Any, seed_group_id: str) -> None:
    client = _api_client(context)
    data = await client.get_seed_group(seed_group_id)
    await _callback_reply(
        update,
        format_seed_group(data),
        reply_markup=seed_group_actions_markup(seed_group_id),
    )


async def _send_seed_group_channels(
    update: Any,
    context: Any,
    seed_group_id: str,
    *,
    offset: int,
) -> None:
    client = _api_client(context)
    group = await client.get_seed_group(seed_group_id)
    data = await client.list_seed_group_channels(seed_group_id)
    await _callback_reply(
        update,
        format_seed_channels(
            data,
            group_name=(group.get("group") or {}).get("name"),
            offset=offset,
            page_size=CHANNEL_PAGE_SIZE,
        ),
        reply_markup=seed_group_pager_markup(
            seed_group_id,
            offset=offset,
            total=data.get("total", 0),
            page_size=CHANNEL_PAGE_SIZE,
            action=ACTION_SEED_CHANNELS,
        ),
    )


async def _send_seed_group_candidates(
    update: Any,
    context: Any,
    seed_group_id: str,
    *,
    offset: int,
) -> None:
    client = _api_client(context)
    group = await client.get_seed_group(seed_group_id)
    data = await client.list_seed_group_candidates(
        seed_group_id,
        limit=CANDIDATE_PAGE_SIZE,
        offset=offset,
    )
    group_name = (group.get("group") or {}).get("name")
    await _callback_reply(
        update,
        format_candidates(data, seed_group_name=group_name, offset=offset),
        reply_markup=seed_group_pager_markup(
            seed_group_id,
            offset=offset,
            total=data.get("total", 0),
            page_size=CANDIDATE_PAGE_SIZE,
            action=ACTION_SEED_CANDIDATES,
        ),
    )
    for index, item in enumerate(data.get("items") or [], start=offset + 1):
        community_id = str((_candidate_community(item)).get("id", "unknown"))
        await _callback_reply(
            update,
            format_candidate_card(item, index=index),
            reply_markup=candidate_actions_markup(community_id),
        )


async def _send_community_detail(update: Any, context: Any, community_id: str) -> None:
    client = _api_client(context)
    detail = await client.get_community(community_id)
    collection_runs = await client.list_collection_runs(community_id)
    await _callback_reply(
        update,
        format_community_detail(detail, collection_runs),
        reply_markup=community_actions_markup(community_id),
    )


async def _send_community_members(
    update: Any,
    context: Any,
    community_id: str,
    *,
    offset: int,
) -> None:
    client = _api_client(context)
    detail = await client.get_community(community_id)
    data = await client.list_community_members(
        community_id,
        limit=MEMBER_PAGE_SIZE,
        offset=offset,
    )
    community = detail.get("community") or {}
    title = community.get("title") or community.get("username") or community_id
    await _callback_reply(
        update,
        format_members(data, community_title=title, offset=offset),
        reply_markup=member_pager_markup(
            community_id,
            offset=offset,
            total=data.get("total", 0),
            page_size=MEMBER_PAGE_SIZE,
        ),
    )


async def _send_engagement_home(update: Any, context: Any) -> None:
    client = _api_client(context)
    pending = await client.list_engagement_candidates(
        status="needs_review",
        limit=1,
        offset=0,
    )
    approved = await client.list_engagement_candidates(
        status="approved",
        limit=1,
        offset=0,
    )
    failed = await client.list_engagement_candidates(
        status="failed",
        limit=1,
        offset=0,
    )
    topics = await client.list_engagement_topics()
    active_topic_count = sum(1 for topic in topics.get("items") or [] if topic.get("active"))
    data = {
        "pending_reply_count": pending.get("total", 0),
        "approved_reply_count": approved.get("total", 0),
        "failed_candidate_count": failed.get("total", 0),
        "active_topic_count": active_topic_count,
    }
    await _callback_reply(update, format_engagement_home(data), reply_markup=engagement_home_markup())


async def _send_engagement_candidates(
    update: Any,
    context: Any,
    *,
    status: str,
    offset: int,
) -> None:
    client = _api_client(context)
    data = await client.list_engagement_candidates(
        status=status,
        limit=ENGAGEMENT_CANDIDATE_PAGE_SIZE,
        offset=offset,
    )
    await _callback_reply(
        update,
        format_engagement_candidates(data, offset=offset, status=status),
        reply_markup=engagement_candidate_filter_markup(status=status),
    )
    for index, item in enumerate(data.get("items") or [], start=offset + 1):
        candidate_id = str(item.get("id", "unknown"))
        candidate_status = str(item.get("status") or status)
        reply_markup = None
        if candidate_status == "approved":
            reply_markup = engagement_candidate_send_markup(candidate_id)
        elif candidate_status in {"needs_review", "failed"}:
            reply_markup = engagement_candidate_actions_markup(candidate_id)
        await _callback_reply(
            update,
            format_engagement_candidate_card(item, index=index),
            reply_markup=reply_markup,
        )
    pager_markup = engagement_candidate_pager_markup(
        offset=offset,
        total=data.get("total", 0),
        page_size=ENGAGEMENT_CANDIDATE_PAGE_SIZE,
        status=status,
    )
    if pager_markup is not None:
        await _callback_reply(update, "Reply page controls", reply_markup=pager_markup)


async def _send_engagement_topics(update: Any, context: Any, *, offset: int) -> None:
    client = _api_client(context)
    data = await client.list_engagement_topics()
    items = data.get("items") or []
    total = int(data.get("total", len(items)) or 0)
    page = items[offset : offset + ENGAGEMENT_TOPIC_PAGE_SIZE]
    page_data = {"items": page, "total": total}

    await _callback_reply(
        update,
        format_engagement_topics(page_data, offset=offset),
        reply_markup=engagement_topic_pager_markup(
            offset=offset,
            total=total,
            page_size=ENGAGEMENT_TOPIC_PAGE_SIZE,
        ),
    )
    for index, item in enumerate(page, start=offset + 1):
        topic_id = str(item.get("id", "unknown"))
        await _callback_reply(
            update,
            format_engagement_topic_card(item, index=index),
            reply_markup=engagement_topic_actions_markup(
                topic_id,
                active=bool(item.get("active")),
            ),
        )


async def _toggle_engagement_topic(
    update: Any,
    context: Any,
    topic_id: str,
    *,
    active: bool,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    data = await client.update_engagement_topic(topic_id, active=active)
    message = format_engagement_topic_card(data)
    reply_markup = engagement_topic_actions_markup(topic_id, active=bool(data.get("active")))
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _reply(update, message, reply_markup=reply_markup)


async def _review_engagement_candidate(
    update: Any,
    context: Any,
    candidate_id: str,
    *,
    action: str,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    reviewer = _reviewer_label(update)
    if action == "approve":
        data = await client.approve_engagement_candidate(candidate_id, reviewed_by=reviewer)
    else:
        data = await client.reject_engagement_candidate(candidate_id, reviewed_by=reviewer)

    message = format_engagement_candidate_review(action, data)
    reply_markup = None
    if data.get("status") == "approved":
        reply_markup = engagement_candidate_send_markup(candidate_id)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _reply(update, message, reply_markup=reply_markup)


async def _send_engagement_reply(update: Any, context: Any, candidate_id: str) -> None:
    client = _api_client(context)
    data = await client.send_engagement_candidate(
        candidate_id,
        approved_by=_reviewer_label(update),
    )
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_engagement_job_response(
            data,
            label="Reply send",
            candidate_id=candidate_id,
        ),
        reply_markup=engagement_job_markup(job_id, candidate_id=candidate_id),
    )


async def _start_seed_group_resolution(update: Any, context: Any, seed_group_id: str) -> None:
    client = _api_client(context)
    data = await client.start_seed_group_resolution(seed_group_id)
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_seed_group_resolution(data),
        reply_markup=job_actions_markup(job_id),
    )


async def _start_collection(update: Any, context: Any, community_id: str) -> None:
    client = _api_client(context)
    detail = await client.get_community(community_id)
    data = await client.start_collection(community_id)
    community = detail.get("community") or {}
    title = community.get("title") or community.get("username")
    await _callback_reply(
        update,
        format_collection_job(data, community_title=title),
        reply_markup=review_result_markup(
            community_id,
            str((data.get("job") or {}).get("id", "unknown")),
        ),
    )


async def _send_job_status(update: Any, context: Any, job_id: str) -> None:
    client = _api_client(context)
    data = await client.get_job(job_id)
    await _callback_reply(update, format_job_status(data), reply_markup=job_actions_markup(job_id))


async def post_init(application: Any) -> None:
    settings: BotSettings = application.bot_data["settings"]
    application.bot_data[API_CLIENT_KEY] = BotApiClient(
        base_url=settings.api_base_url,
        api_token=settings.api_token,
        timeout_seconds=settings.request_timeout_seconds,
    )


async def post_shutdown(application: Any) -> None:
    client = application.bot_data.get(API_CLIENT_KEY)
    if client is not None:
        await client.aclose()


def create_application(settings: BotSettings | None = None) -> Any:
    try:
        from telegram import Update
        from telegram.ext import (
            Application,
            CallbackQueryHandler,
            CommandHandler,
            MessageHandler,
            TypeHandler,
            filters,
        )
    except ImportError as exc:
        raise RuntimeError("python-telegram-bot must be installed before the bot can run") from exc

    runtime_settings = settings or load_settings()
    validate_runtime_settings(runtime_settings)

    application = (
        Application.builder()
        .token(runtime_settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["settings"] = runtime_settings
    application.add_handler(TypeHandler(Update, access_gate), group=-1)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("whoami", whoami_command))
    application.add_handler(CommandHandler("brief", brief_command))
    application.add_handler(CommandHandler("briefs", briefs_command))
    application.add_handler(CommandHandler("entity", entity_command))
    application.add_handler(CommandHandler("candidates", candidates_command))
    application.add_handler(CommandHandler("approve", approve_command))
    application.add_handler(CommandHandler("reject", reject_command))
    application.add_handler(CommandHandler("job", job_command))
    application.add_handler(CommandHandler("accounts", accounts_command))
    application.add_handler(CommandHandler("seeds", seeds_command))
    application.add_handler(CommandHandler("seed", seed_command))
    application.add_handler(CommandHandler("channels", channels_command))
    application.add_handler(CommandHandler("resolveseeds", resolveseeds_command))
    application.add_handler(CommandHandler("community", community_command))
    application.add_handler(CommandHandler("collect", collect_command))
    application.add_handler(CommandHandler("members", members_command))
    application.add_handler(CommandHandler("exportmembers", exportmembers_command))
    application.add_handler(CommandHandler("engagement", engagement_command))
    application.add_handler(CommandHandler("engagement_topics", engagement_topics_command))
    application.add_handler(CommandHandler("create_engagement_topic", create_engagement_topic_command))
    application.add_handler(CommandHandler("toggle_engagement_topic", toggle_engagement_topic_command))
    application.add_handler(CommandHandler("engagement_candidates", engagement_candidates_command))
    application.add_handler(CommandHandler("approve_reply", approve_reply_command))
    application.add_handler(CommandHandler("reject_reply", reject_reply_command))
    application.add_handler(CommandHandler("send_reply", send_reply_command))
    application.add_handler(CallbackQueryHandler(callback_query))
    application.add_handler(MessageHandler(filters.Regex(f"^{SEEDS_MENU_LABEL}$"), seeds_command))
    application.add_handler(
        MessageHandler(filters.Regex(f"^{ACCOUNTS_MENU_LABEL}$"), accounts_command)
    )
    application.add_handler(
        MessageHandler(filters.Regex(f"^{ENGAGEMENT_MENU_LABEL}$"), engagement_command)
    )
    application.add_handler(MessageHandler(filters.Regex(f"^{HELP_MENU_LABEL}$"), help_command))
    application.add_handler(MessageHandler(filters.Document.FileExtension("csv"), seed_csv_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_entity_text))
    return application


def main() -> None:
    application = create_application()
    application.run_polling()


def _api_client(context: Any) -> BotApiClient:
    return context.application.bot_data[API_CLIENT_KEY]


def _first_arg(context: Any) -> str | None:
    if not context.args:
        return None
    value = context.args[0].strip()
    return value or None


def _second_arg_as_offset(context: Any) -> int:
    if len(context.args) < 2:
        return 0
    return _parse_offset(context.args[1])


def _engagement_candidate_status_arg(context: Any) -> str:
    status = _first_arg(context) or "needs_review"
    if status not in ENGAGEMENT_CANDIDATE_STATUSES:
        return "needs_review"
    return status


def _engagement_callback_status_and_offset(parts: list[str]) -> tuple[str, int]:
    if len(parts) >= 2:
        raw_status = parts[0]
        status = raw_status if raw_status in ENGAGEMENT_CANDIDATE_STATUSES else "needs_review"
        return status, _parse_offset(parts[1])
    return "needs_review", _parse_offset(parts[0])


def _parse_create_engagement_topic_args(context: Any) -> tuple[str, str, list[str]] | None:
    raw_value = " ".join(str(arg) for arg in context.args).strip()
    parts = [part.strip() for part in raw_value.split("|")]
    if len(parts) != 3:
        return None

    name, guidance, raw_keywords = parts
    keywords = [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]
    if not name or not guidance or not keywords:
        return None
    return name, guidance, keywords


def _create_engagement_topic_usage() -> str:
    return "\n".join(
        [
            "Usage: /create_engagement_topic <name> | <guidance> | <comma_keywords>",
            "Include at least one trigger keyword.",
            "Example: /create_engagement_topic Open CRM | Be factual and brief. | crm, open source",
        ]
    )


def _parse_on_off(raw_value: str) -> bool | None:
    value = raw_value.strip().casefold()
    if value == "on":
        return True
    if value == "off":
        return False
    return None


def _candidate_community(item: dict[str, Any]) -> dict[str, Any]:
    community = item.get("community")
    if isinstance(community, dict):
        return community
    return item


def _parse_offset(raw_value: str) -> int:
    try:
        return max(int(raw_value), 0)
    except ValueError:
        return 0


def _is_authorized_update(update: Any, settings: BotSettings) -> bool:
    if not settings.allowed_user_ids:
        return True
    user_id = _telegram_user_id(update)
    return user_id in settings.allowed_user_ids if user_id is not None else False


def _is_identity_command(update: Any) -> bool:
    return _message_command_name(update) == "whoami"


def _message_command_name(update: Any) -> str | None:
    message = getattr(update, "message", None)
    text = getattr(message, "text", None)
    if not isinstance(text, str) or not text.startswith("/"):
        return None
    first_token = text.split(maxsplit=1)[0].lstrip("/")
    command = first_token.split("@", maxsplit=1)[0].lower()
    return command or None


def _telegram_user(update: Any) -> Any | None:
    effective_user = getattr(update, "effective_user", None)
    if effective_user is not None:
        return effective_user

    message = getattr(update, "message", None)
    message_user = getattr(message, "from_user", None)
    if message_user is not None:
        return message_user

    query = getattr(update, "callback_query", None)
    return getattr(query, "from_user", None)


def _telegram_user_id(update: Any) -> int | None:
    user = _telegram_user(update)
    raw_user_id = getattr(user, "id", None)
    if raw_user_id is None:
        return None
    try:
        return int(raw_user_id)
    except (TypeError, ValueError):
        return None


def _telegram_username(user: Any | None) -> str | None:
    username = getattr(user, "username", None)
    return username if isinstance(username, str) and username else None


def _reviewer_label(update: Any) -> str:
    user = _telegram_user(update)
    user_id = _telegram_user_id(update)
    if user_id is None:
        return "telegram_bot"
    username = _telegram_username(user)
    if username:
        return f"telegram:{user_id}:@{username}"
    return f"telegram:{user_id}"


async def _deny_access(update: Any) -> None:
    user = _telegram_user(update)
    user_id = _telegram_user_id(update)
    message = format_access_denied(user_id, username=_telegram_username(user))

    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.answer(message, show_alert=True)
        return

    await _reply(update, message)


def _looks_like_telegram_reference(raw_value: str) -> bool:
    value = raw_value.strip()
    if not value or any(character.isspace() for character in value):
        return False
    lowered = value.lower()
    return value.startswith("@") or lowered.startswith(("https://t.me/", "http://t.me/", "t.me/", "telegram.me/"))


async def _callback_reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    query = update.callback_query
    if query is not None and query.message is not None:
        await query.message.reply_text(text, reply_markup=reply_markup)
        return
    await _reply(update, text, reply_markup=reply_markup)


async def _edit_callback_message(update: Any, text: str, reply_markup: Any | None = None) -> None:
    query = update.callback_query
    if query is not None:
        await query.edit_message_text(text=text, reply_markup=reply_markup)


async def _reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    if update.message is not None:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def _reply_document(
    update: Any,
    *,
    document_bytes: bytes,
    file_name: str,
    caption: str,
) -> None:
    if update.message is None:
        return
    document = io.BytesIO(document_bytes)
    document.name = file_name
    await update.message.reply_document(document=document, filename=file_name, caption=caption)


async def _fetch_all_community_members(client: BotApiClient, community_id: str) -> dict[str, Any]:
    offset = 0
    total: int | None = None
    items: list[dict[str, Any]] = []
    while total is None or offset < total:
        page = await client.list_community_members(
            community_id,
            limit=MEMBER_EXPORT_PAGE_SIZE,
            offset=offset,
        )
        page_items = page.get("items") or []
        if not page_items:
            total = page.get("total", len(items))
            break
        items.extend(page_items)
        total = int(page.get("total", len(items)))
        offset += len(page_items)
    return {"items": items, "total": total if total is not None else len(items)}


def _members_csv_bytes(items: list[dict[str, Any]]) -> bytes:
    output = io.StringIO()
    fieldnames = [
        "tg_user_id",
        "username",
        "first_name",
        "membership_status",
        "activity_status",
        "first_seen_at",
        "last_updated_at",
        "last_active_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow({field: item.get(field) for field in fieldnames})
    return output.getvalue().encode("utf-8")


if __name__ == "__main__":
    main()
