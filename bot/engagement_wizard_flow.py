# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from typing import Any

from .runtime import *


_WIZARD_LEVEL_MODE = {
    "watching": "observe",
    "suggesting": "suggest",
    "sending": "require_approval",
}


def _wizard_return_save(context: Any, operator_id: int, state: dict[str, Any]) -> None:
    store = context.application.bot_data.setdefault(WIZARD_RETURN_STORE_KEY, {})
    store[operator_id] = dict(state)


def _wizard_return_pop(context: Any, operator_id: int) -> dict[str, Any] | None:
    store = context.application.bot_data.get(WIZARD_RETURN_STORE_KEY) or {}
    return store.pop(operator_id, None)


def _wizard_state(pending: Any) -> dict[str, Any]:
    return dict(pending.flow_state or {})


def _wizard_topic_ids(state: dict[str, Any]) -> list[str]:
    ids = state.get("topic_ids")
    return list(ids) if ids else []


async def _start_engagement_wizard(
    update: Any,
    context: Any,
    *,
    target_ref: str | None = None,
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _reply(update, "Telegram did not include a user ID on this update.")
        return
    editable = editable_field("wizard", "state")
    if editable is None:
        await _reply(update, "Wizard is not available right now.")
        return

    # Check for pre-supplied target_ref (from command argument)
    if target_ref:
        if not _looks_like_telegram_reference(target_ref):
            await _reply(update, "That doesn't look like a @handle or t.me/... link.")
            return
        pending = _config_edit_store(context).start(
            operator_id=operator_id,
            field=editable,
            object_id="new",
            flow_step="community",
            flow_state={"community_id": None, "target_id": None, "community_ref": None,
                        "topic_ids": [], "account_id": None, "level": None},
        )
        await _wizard_resolve_community(update, context, operator_id, pending, target_ref)
        return

    # Check for resumable state
    existing = _config_edit_store(context).get(operator_id)
    if existing and existing.entity == "wizard":
        state = _wizard_state(existing)
        if state.get("community_id"):
            await _wizard_show_appropriate_step(update, context, operator_id, state)
            return

    # Start fresh
    pending = _config_edit_store(context).start(
        operator_id=operator_id,
        field=editable,
        object_id="new",
        flow_step="community",
        flow_state={"community_id": None, "target_id": None, "community_ref": None,
                    "topic_ids": [], "account_id": None, "level": None},
    )
    await _show_wizard_step1(update, context)


async def _show_wizard_step1(update: Any, context: Any) -> None:
    await _callback_reply(update, format_wizard_community_prompt())


async def _wizard_resolve_community(
    update: Any,
    context: Any,
    operator_id: int,
    pending: Any,
    raw_ref: str,
) -> None:
    client = _api_client(context)
    reviewer = _reviewer_label(update)
    try:
        data = await client.create_engagement_target(
            target_ref=raw_ref,
            added_by=reviewer,
            operator_user_id=operator_id,
        )
    except BotApiError as exc:
        await _reply(update, f"Couldn't add that community: {exc.message}\n\nTry again or /cancel_edit.")
        return

    target_id = str(data.get("id") or "")
    community_id = str(data.get("community_id") or target_id)
    status = str(data.get("status") or "pending")
    community_ref = str(data.get("submitted_ref") or raw_ref)

    if status == "approved":
        _config_edit_store(context).cancel(operator_id)
        await _reply(update, f"✅ {community_ref} is already active in the engagement system. Use /engagement to open the cockpit.")
        return

    state: dict[str, Any] = {
        "community_id": community_id,
        "target_id": target_id,
        "community_ref": community_ref,
        "topic_ids": [],
        "account_id": None,
        "level": None,
    }
    _config_edit_store(context).set_value(
        operator_id,
        raw_value=raw_ref,
        parsed_value=None,
        flow_step="topics",
        flow_state=state,
    )
    await _show_wizard_step2(update, context, state)


async def _show_wizard_step2(update: Any, context: Any, state: dict[str, Any]) -> None:
    client = _api_client(context)
    community_ref = str(state.get("community_ref") or state.get("community_id") or "")
    selected_ids = _wizard_topic_ids(state)
    try:
        data = await client.list_engagement_topics()
    except BotApiError as exc:
        await _callback_reply(update, f"Couldn't load topics: {exc.message}")
        return
    topics = data.get("items") or []
    community_id = str(state.get("community_id") or "")
    markup = engagement_wizard_topics_markup(
        topics,
        selected_ids=selected_ids,
        community_id=community_id,
        has_selection=bool(selected_ids),
    )
    await _callback_reply(update, format_wizard_topics_prompt(topics, community_ref=community_ref, selected_ids=selected_ids), reply_markup=markup)


async def _show_wizard_step3(update: Any, context: Any, state: dict[str, Any]) -> None:
    client = _api_client(context)
    community_ref = str(state.get("community_ref") or state.get("community_id") or "")
    community_id = str(state.get("community_id") or "")
    try:
        data = await client.get_accounts()
    except BotApiError as exc:
        await _callback_reply(update, f"Couldn't load accounts: {exc.message}")
        return
    all_accounts = data.get("items") or []
    engagement_accounts = [
        a for a in all_accounts
        if a.get("pool") in ("engagement", None) and a.get("status") != "banned"
    ]
    if len(engagement_accounts) == 0:
        await _callback_reply(
            update,
            format_wizard_account_prompt([], community_ref=community_ref),
            reply_markup=engagement_wizard_accounts_markup([], community_id=community_id),
        )
        return
    if len(engagement_accounts) == 1:
        await _wizard_pick_account(update, context, str(engagement_accounts[0].get("id") or ""), state)
        return
    markup = engagement_wizard_accounts_markup(engagement_accounts, community_id=community_id)
    await _callback_reply(update, format_wizard_account_prompt(engagement_accounts, community_ref=community_ref), reply_markup=markup)


async def _show_wizard_step4(update: Any, context: Any, state: dict[str, Any]) -> None:
    community_ref = str(state.get("community_ref") or state.get("community_id") or "")
    community_id = str(state.get("community_id") or "")
    topic_ids = _wizard_topic_ids(state)
    topic_names = list(topic_ids)  # fallback; ideally fetched, but we only have IDs here
    await _callback_reply(
        update,
        format_wizard_level_prompt(community_ref=community_ref, selected_topics=topic_names),
        reply_markup=engagement_wizard_level_markup(community_id),
    )


async def _show_wizard_step5(update: Any, context: Any, state: dict[str, Any]) -> None:
    community_ref = str(state.get("community_ref") or state.get("community_id") or "")
    community_id = str(state.get("community_id") or "")
    topic_ids = _wizard_topic_ids(state)
    account_id = str(state.get("account_id") or "")
    level = str(state.get("level") or "suggesting")
    client = _api_client(context)
    topic_names: list[str] = []
    account_phone = account_id
    try:
        topics_data = await client.list_engagement_topics()
        topics_by_id = {str(t.get("id") or ""): str(t.get("name") or "") for t in (topics_data.get("items") or [])}
        topic_names = [topics_by_id.get(tid, tid) for tid in topic_ids]
    except BotApiError:
        topic_names = topic_ids
    try:
        accounts_data = await client.get_accounts()
        for acct in (accounts_data.get("items") or []):
            if str(acct.get("id") or "") == account_id:
                account_phone = str(acct.get("phone") or account_id)
                break
    except BotApiError:
        pass
    markup = engagement_wizard_launch_markup(community_id)
    await _callback_reply(
        update,
        format_wizard_launch_card(
            community_ref=community_ref,
            topic_names=topic_names,
            account_phone=account_phone,
            level=level,
        ),
        reply_markup=markup,
    )


async def _wizard_show_appropriate_step(
    update: Any,
    context: Any,
    operator_id: int,
    state: dict[str, Any],
) -> None:
    community_id = str(state.get("community_id") or "")
    topic_ids = _wizard_topic_ids(state)
    account_id = state.get("account_id")
    level = state.get("level")

    if not community_id:
        await _show_wizard_step1(update, context)
        return
    if not topic_ids:
        await _show_wizard_step2(update, context, state)
        return
    if not account_id:
        await _show_wizard_step3(update, context, state)
        return
    if not level:
        await _show_wizard_step4(update, context, state)
        return
    await _show_wizard_step5(update, context, state)


async def _handle_wizard_text(
    update: Any,
    context: Any,
    pending: Any,
    raw_text: str,
) -> bool:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return False

    step = pending.flow_step or "community"
    if step != "community":
        await _reply(update, "Use the buttons to continue the wizard, or /cancel_edit to stop.")
        return True

    text = raw_text.strip()
    if not _looks_like_telegram_reference(text):
        await _reply(
            update,
            "That doesn't look like a @handle or t.me/... link.\n\n" + format_wizard_community_prompt(),
        )
        return True

    await _wizard_resolve_community(update, context, operator_id, pending, text)
    return True


async def _handle_wizard_callback(update: Any, context: Any, parts: list[str]) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return

    sub = parts[0] if parts else "start"

    if sub == "start":
        await _start_engagement_wizard(update, context)
        return

    if sub == "step" and len(parts) >= 3:
        step_num = parts[1]
        community_id = parts[2]
        await _handle_wizard_navigate_step(update, context, operator_id, step_num, community_id)
        return

    if sub == "tp" and len(parts) >= 2:
        topic_id = parts[1]
        await _handle_wizard_toggle_topic(update, context, operator_id, topic_id)
        return

    if sub == "tn":
        await _handle_wizard_topic_new(update, context, operator_id)
        return

    if sub == "ap" and len(parts) >= 2:
        account_id = parts[1]
        await _handle_wizard_account_pick(update, context, operator_id, account_id)
        return

    if sub == "an" and len(parts) >= 2:
        community_id = parts[1]
        await _callback_reply(update, "Add an engagement account with /add_account, then restart the wizard.")
        return

    if sub == "lv" and len(parts) >= 3:
        level = parts[1]
        community_id = parts[2]
        await _handle_wizard_level(update, context, operator_id, level, community_id)
        return

    if sub == "go" and len(parts) >= 2:
        community_id = parts[1]
        await _handle_wizard_launch(update, context, operator_id, community_id)
        return

    if sub == "retry" and len(parts) >= 2:
        community_id = parts[1]
        await _handle_wizard_launch(update, context, operator_id, community_id)
        return

    await _callback_reply(update, "Unknown wizard action.")


async def _handle_wizard_navigate_step(
    update: Any,
    context: Any,
    operator_id: int,
    step_num: str,
    community_id: str,
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Wizard session expired. Use /add_engagement_target to start again.")
        return
    state = _wizard_state(pending)
    n = step_num
    if n == "2":
        await _show_wizard_step2(update, context, state)
    elif n == "3":
        topic_ids = _wizard_topic_ids(state)
        if not topic_ids:
            await _callback_reply(update, "Pick at least one topic first.")
            return
        # Force selected topics active
        await _wizard_activate_topics(update, context, operator_id, topic_ids)
        state_updated = _wizard_state(_config_edit_store(context).get(operator_id) or pending)
        await _show_wizard_step3(update, context, state_updated)
    elif n == "4":
        await _show_wizard_step4(update, context, state)
    elif n == "5":
        await _show_wizard_step5(update, context, state)
    else:
        await _show_wizard_step1(update, context)


async def _wizard_activate_topics(
    update: Any,
    context: Any,
    operator_id: int,
    topic_ids: list[str],
) -> None:
    client = _api_client(context)
    for topic_id in topic_ids:
        try:
            await client.update_engagement_topic(
                topic_id,
                active=True,
                operator_user_id=operator_id,
            )
        except BotApiError:
            pass  # Best-effort; don't block wizard for this


async def _handle_wizard_toggle_topic(
    update: Any,
    context: Any,
    operator_id: int,
    topic_id: str,
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Wizard session expired. Use /add_engagement_target to start again.")
        return
    state = _wizard_state(pending)
    topic_ids = _wizard_topic_ids(state)
    if topic_id in topic_ids:
        topic_ids.remove(topic_id)
    else:
        topic_ids.append(topic_id)
    state["topic_ids"] = topic_ids
    _config_edit_store(context).set_value(
        operator_id,
        raw_value="",
        parsed_value=None,
        flow_step="topics",
        flow_state=state,
    )
    await _show_wizard_step2_edit(update, context, state)


async def _show_wizard_step2_edit(update: Any, context: Any, state: dict[str, Any]) -> None:
    client = _api_client(context)
    community_ref = str(state.get("community_ref") or state.get("community_id") or "")
    community_id = str(state.get("community_id") or "")
    selected_ids = _wizard_topic_ids(state)
    try:
        data = await client.list_engagement_topics()
    except BotApiError as exc:
        await _callback_reply(update, f"Couldn't load topics: {exc.message}")
        return
    topics = data.get("items") or []
    markup = engagement_wizard_topics_markup(
        topics,
        selected_ids=selected_ids,
        community_id=community_id,
        has_selection=bool(selected_ids),
    )
    await _edit_callback_message(
        update,
        format_wizard_topics_prompt(topics, community_ref=community_ref, selected_ids=selected_ids),
        reply_markup=markup,
    )


async def _handle_wizard_topic_new(
    update: Any,
    context: Any,
    operator_id: int,
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Wizard session expired. Use /add_engagement_target to start again.")
        return
    wizard_state = _wizard_state(pending)
    _wizard_return_save(context, operator_id, wizard_state)
    editable = editable_field("topic_create", "payload")
    if editable is None:
        await _callback_reply(update, "Topic creation is not available right now.")
        return
    new_pending = _config_edit_store(context).start(
        operator_id=operator_id,
        field=editable,
        object_id="new",
        flow_step="name",
        flow_state={},
    )
    await _callback_reply(update, render_edit_request(new_pending))


async def _handle_wizard_account_pick(
    update: Any,
    context: Any,
    operator_id: int,
    account_id: str,
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Wizard session expired. Use /add_engagement_target to start again.")
        return
    state = _wizard_state(pending)
    community_id = str(state.get("community_id") or "")
    state["account_id"] = account_id
    _config_edit_store(context).set_value(
        operator_id,
        raw_value=account_id,
        parsed_value=None,
        flow_step="account",
        flow_state=state,
    )
    await _callback_reply(update, "Joining community… ⏳")
    client = _api_client(context)
    # Update settings with assigned account
    try:
        current = await client.get_engagement_settings(community_id)
        payload = _engagement_settings_payload_from_current(
            current,
            assigned_account_id=account_id,
            allow_join=True,
        )
        await client.update_engagement_settings(community_id, **payload, operator_user_id=operator_id)
    except BotApiError as exc:
        await _reply(update, f"Couldn't assign account: {exc.message}")
    # Trigger join
    try:
        await client.start_community_join(
            community_id,
            telegram_account_id=account_id,
            requested_by=_reviewer_label(update),
        )
    except BotApiError:
        pass  # join failure is non-fatal for wizard
    await _show_wizard_step4(update, context, state)


async def _wizard_pick_account(
    update: Any,
    context: Any,
    account_id: str,
    state: dict[str, Any],
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return
    await _handle_wizard_account_pick(update, context, operator_id, account_id)


async def _handle_wizard_level(
    update: Any,
    context: Any,
    operator_id: int,
    level: str,
    community_id: str,
) -> None:
    if level not in _WIZARD_LEVEL_MODE:
        await _callback_reply(update, f"Unknown level: {level}.")
        return
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Wizard session expired. Use /add_engagement_target to start again.")
        return
    state = _wizard_state(pending)
    state["level"] = level
    _config_edit_store(context).set_value(
        operator_id,
        raw_value=level,
        parsed_value=None,
        flow_step="level",
        flow_state=state,
    )
    mode = _WIZARD_LEVEL_MODE[level]
    allow_post = level == "sending"
    client = _api_client(context)
    try:
        current = await client.get_engagement_settings(community_id)
        payload = _engagement_settings_payload_from_current(
            current,
            mode=mode,
            allow_join=True,
            allow_post=allow_post,
        )
        await client.update_engagement_settings(community_id, **payload, operator_user_id=operator_id)
    except BotApiError as exc:
        await _callback_reply(update, f"Couldn't save level: {exc.message}")
        return
    target_id = str(state.get("target_id") or "")
    if target_id:
        try:
            await client.update_engagement_target(
                target_id,
                allow_detect=True,
                allow_join=True,
                allow_post=allow_post,
                operator_user_id=operator_id,
            )
        except BotApiError:
            pass
    await _show_wizard_step5(update, context, state)


async def _handle_wizard_launch(
    update: Any,
    context: Any,
    operator_id: int,
    community_id: str,
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Wizard session expired. Use /add_engagement_target to start again.")
        return
    state = _wizard_state(pending)
    target_id = str(state.get("target_id") or "")
    client = _api_client(context)
    # Enqueue detect job first (atomic gate)
    try:
        await client.start_engagement_detection(
            community_id,
            requested_by=_reviewer_label(update),
        )
    except BotApiError as exc:
        await _edit_callback_message(
            update,
            f"Could not start engagement detection: {exc.message}\n\nUse Retry to try again.",
            reply_markup=engagement_wizard_retry_markup(community_id),
        )
        return
    # Approve target
    if target_id:
        try:
            await client.update_engagement_target(
                target_id,
                status="approved",
                operator_user_id=operator_id,
            )
        except BotApiError:
            pass
    _config_edit_store(context).cancel(operator_id)
    await _edit_callback_message(
        update,
        "🎉 Started ✓ — first results will appear in the cockpit shortly. Use /engagement to view.",
    )


async def _wizard_resume_after_topic_create(
    update: Any,
    context: Any,
    wizard_state: dict[str, Any],
    topic_data: dict[str, Any],
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return
    editable = editable_field("wizard", "state")
    if editable is None:
        return
    new_topic_id = str(topic_data.get("id") or "")
    topic_ids = _wizard_topic_ids(wizard_state)
    if new_topic_id and new_topic_id not in topic_ids:
        topic_ids.append(new_topic_id)
    wizard_state["topic_ids"] = topic_ids
    _config_edit_store(context).start(
        operator_id=operator_id,
        field=editable,
        object_id=str(wizard_state.get("community_id") or "new"),
        flow_step="topics",
        flow_state=wizard_state,
    )
    await _show_wizard_step2(update, context, wizard_state)


__all__ = [
    "_start_engagement_wizard",
    "_handle_wizard_callback",
    "_handle_wizard_text",
    "_wizard_resume_after_topic_create",
    "_wizard_return_pop",
]
