# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from typing import Any

from .runtime import *


# ---------------------------------------------------------------------------
# Mode mapping: wizard "level" labels → API mode values
# ---------------------------------------------------------------------------

_WIZARD_LEVEL_MODE = {
    "watching": "observe",
    "suggesting": "suggest",
    "sending": "require_approval",
}


# ---------------------------------------------------------------------------
# Wizard state helpers
# New state shape: {engagement_id, target_id, topic_id, account_id, mode,
#                   target_ref, return_callback}
# ---------------------------------------------------------------------------


def _wizard_state(pending: Any) -> dict[str, Any]:
    return dict(pending.flow_state or {})


def _wizard_state_engagement_id(state: dict[str, Any]) -> str:
    return str(state.get("engagement_id") or "")


def _wizard_state_topic_id(state: dict[str, Any]) -> str | None:
    return state.get("topic_id") or None


def _wizard_state_account_id(state: dict[str, Any]) -> str | None:
    return state.get("account_id") or None


def _wizard_state_mode(state: dict[str, Any]) -> str | None:
    return state.get("mode") or None


# ---------------------------------------------------------------------------
# Start / entry points
# ---------------------------------------------------------------------------


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
        _config_edit_store(context).start(
            operator_id=operator_id,
            field=editable,
            object_id="new",
            flow_step="target",
            flow_state=_fresh_wizard_state(),
        )
        await _wizard_resolve_target(update, context, operator_id, target_ref)
        return

    # Check for resumable state
    existing = _config_edit_store(context).get(operator_id)
    if existing and existing.entity == "wizard":
        state = _wizard_state(existing)
        if state.get("engagement_id"):
            await _wizard_show_appropriate_step(update, context, operator_id, state)
            return

    # Start fresh
    _config_edit_store(context).start(
        operator_id=operator_id,
        field=editable,
        object_id="new",
        flow_step="target",
        flow_state=_fresh_wizard_state(),
    )
    await _show_wizard_step1(update, context)


def _fresh_wizard_state() -> dict[str, Any]:
    return {
        "engagement_id": None,
        "target_id": None,
        "target_ref": None,
        "topic_id": None,
        "account_id": None,
        "mode": None,
        "return_callback": None,
    }


# ---------------------------------------------------------------------------
# Step 1: Target entry
# ---------------------------------------------------------------------------


async def _show_wizard_step1(update: Any, context: Any) -> None:
    await _callback_reply(update, format_wizard_community_prompt())


# ---------------------------------------------------------------------------
# Step 1 → resolve target → create engagement
# ---------------------------------------------------------------------------


async def _wizard_resolve_target(
    update: Any,
    context: Any,
    operator_id: int,
    raw_ref: str,
) -> None:
    client = _api_client(context)
    reviewer = _reviewer_label(update)

    # First resolve the target reference into a target record
    try:
        target_data = await client.create_engagement_target(
            target_ref=raw_ref,
            added_by=reviewer,
            operator_user_id=operator_id,
        )
    except BotApiError as exc:
        await _reply(update, f"Couldn't add that community: {exc.message}\n\nTry again or /cancel_edit.")
        return

    target_id = str(target_data.get("id") or "")
    target_status = str(target_data.get("status") or "pending")
    target_ref_saved = str(target_data.get("submitted_ref") or raw_ref)

    if target_status == "approved":
        _config_edit_store(context).cancel(operator_id)
        await _reply(
            update,
            f"✅ {target_ref_saved} is already active in the engagement system. Use /engagement to open the cockpit.",
        )
        return

    # Create the draft engagement
    try:
        eng_data = await client.create_engagement(
            target_id=target_id,
            created_by=reviewer,
        )
    except BotApiError as exc:
        await _reply(update, f"Couldn't create engagement: {exc.message}\n\nTry again or /cancel_edit.")
        return

    engagement = eng_data.get("engagement") or eng_data
    engagement_id = str(engagement.get("id") or "")

    state: dict[str, Any] = {
        "engagement_id": engagement_id,
        "target_id": target_id,
        "target_ref": target_ref_saved,
        "topic_id": None,
        "account_id": None,
        "mode": None,
        "return_callback": None,
    }
    _config_edit_store(context).set_value(
        operator_id,
        raw_value=raw_ref,
        parsed_value=None,
        flow_step="topics",
        flow_state=state,
    )
    await _show_wizard_step2(update, context, state)


# ---------------------------------------------------------------------------
# Step 2: Topic picker
# ---------------------------------------------------------------------------


async def _show_wizard_step2(update: Any, context: Any, state: dict[str, Any]) -> None:
    client = _api_client(context)
    target_ref = str(state.get("target_ref") or state.get("target_id") or "")
    engagement_id = _wizard_state_engagement_id(state)
    selected_id = _wizard_state_topic_id(state)
    try:
        data = await client.list_engagement_topics()
    except BotApiError as exc:
        await _callback_reply(update, f"Couldn't load topics: {exc.message}")
        return
    topics = data.get("items") or []
    markup = engagement_wizard_topics_markup(
        topics,
        selected_id=selected_id,
        engagement_id=engagement_id,
        has_selection=bool(selected_id),
    )
    await _callback_reply(
        update,
        format_wizard_topics_prompt(topics, community_ref=target_ref, selected_ids=[selected_id] if selected_id else []),
        reply_markup=markup,
    )


# ---------------------------------------------------------------------------
# Step 3: Account picker
# ---------------------------------------------------------------------------


async def _show_wizard_step3(update: Any, context: Any, state: dict[str, Any]) -> None:
    client = _api_client(context)
    target_ref = str(state.get("target_ref") or state.get("target_id") or "")
    engagement_id = _wizard_state_engagement_id(state)
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
            format_wizard_account_prompt([], community_ref=target_ref),
            reply_markup=engagement_wizard_accounts_markup([], engagement_id=engagement_id),
        )
        return
    if len(engagement_accounts) == 1:
        await _wizard_pick_account(update, context, str(engagement_accounts[0].get("id") or ""), state)
        return
    markup = engagement_wizard_accounts_markup(engagement_accounts, engagement_id=engagement_id)
    await _callback_reply(
        update,
        format_wizard_account_prompt(engagement_accounts, community_ref=target_ref),
        reply_markup=markup,
    )


# ---------------------------------------------------------------------------
# Step 4: Mode picker
# ---------------------------------------------------------------------------


async def _show_wizard_step4(update: Any, context: Any, state: dict[str, Any]) -> None:
    target_ref = str(state.get("target_ref") or state.get("target_id") or "")
    engagement_id = _wizard_state_engagement_id(state)
    topic_id = _wizard_state_topic_id(state)
    topic_names: list[str] = [topic_id] if topic_id else []
    # Try to resolve topic name
    client = _api_client(context)
    try:
        topics_data = await client.list_engagement_topics()
        topics_by_id = {str(t.get("id") or ""): str(t.get("name") or "") for t in (topics_data.get("items") or [])}
        topic_names = [topics_by_id.get(tid, tid) for tid in ([topic_id] if topic_id else [])]
    except BotApiError:
        pass
    await _callback_reply(
        update,
        format_wizard_level_prompt(community_ref=target_ref, selected_topics=topic_names),
        reply_markup=engagement_wizard_level_markup(engagement_id),
    )


# ---------------------------------------------------------------------------
# Step 5: Review + confirm
# ---------------------------------------------------------------------------


async def _show_wizard_step5(update: Any, context: Any, state: dict[str, Any]) -> None:
    target_ref = str(state.get("target_ref") or state.get("target_id") or "")
    engagement_id = _wizard_state_engagement_id(state)
    topic_id = _wizard_state_topic_id(state)
    account_id = _wizard_state_account_id(state)
    mode = _wizard_state_mode(state) or "suggesting"
    client = _api_client(context)
    # Resolve topic name
    topic_names: list[str] = [topic_id] if topic_id else []
    account_phone = account_id or ""
    try:
        topics_data = await client.list_engagement_topics()
        topics_by_id = {str(t.get("id") or ""): str(t.get("name") or "") for t in (topics_data.get("items") or [])}
        topic_names = [topics_by_id.get(tid, tid) for tid in ([topic_id] if topic_id else [])]
    except BotApiError:
        pass
    # Resolve account phone
    try:
        accounts_data = await client.get_accounts()
        for acct in (accounts_data.get("items") or []):
            if str(acct.get("id") or "") == account_id:
                account_phone = str(acct.get("phone") or account_id)
                break
    except BotApiError:
        pass
    markup = engagement_wizard_launch_markup(engagement_id)
    await _callback_reply(
        update,
        format_wizard_launch_card(
            community_ref=target_ref,
            topic_names=topic_names,
            account_phone=account_phone or "(none)",
            level=mode,
        ),
        reply_markup=markup,
    )


# ---------------------------------------------------------------------------
# Step routing
# ---------------------------------------------------------------------------


async def _wizard_show_appropriate_step(
    update: Any,
    context: Any,
    operator_id: int,
    state: dict[str, Any],
) -> None:
    engagement_id = _wizard_state_engagement_id(state)
    topic_id = _wizard_state_topic_id(state)
    account_id = _wizard_state_account_id(state)
    mode = _wizard_state_mode(state)

    if not engagement_id:
        await _show_wizard_step1(update, context)
        return
    if not topic_id:
        await _show_wizard_step2(update, context, state)
        return
    if not account_id:
        await _show_wizard_step3(update, context, state)
        return
    if not mode:
        await _show_wizard_step4(update, context, state)
        return
    await _show_wizard_step5(update, context, state)


# ---------------------------------------------------------------------------
# Text handler (Step 1: user types target URL/handle)
# ---------------------------------------------------------------------------


async def _handle_wizard_text(
    update: Any,
    context: Any,
    pending: Any,
    raw_text: str,
) -> bool:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return False

    step = pending.flow_step or "target"
    if step != "target":
        await _reply(update, "Use the buttons to continue the wizard, or /cancel_edit to stop.")
        return True

    text = raw_text.strip()
    if not _looks_like_telegram_reference(text):
        await _reply(
            update,
            "That doesn't look like a @handle or t.me/... link.\n\n" + format_wizard_community_prompt(),
        )
        return True

    await _wizard_resolve_target(update, context, operator_id, text)
    return True


# ---------------------------------------------------------------------------
# Callback handler
# ---------------------------------------------------------------------------


async def _handle_wizard_callback(update: Any, context: Any, parts: list[str]) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return

    sub = parts[0] if parts else "start"

    if sub == "start":
        await _start_engagement_wizard(update, context)
        return

    # eng:wz:edit:<engagement_id>:<field>  → edit-reentry
    if sub == "edit" and len(parts) >= 3:
        engagement_id = parts[1]
        field = parts[2]
        await _handle_wizard_edit_reentry(update, context, operator_id, engagement_id, field)
        return

    # eng:wz:step:<step>:<engagement_id>
    if sub == "step" and len(parts) >= 3:
        step_num = parts[1]
        engagement_id = parts[2]
        await _handle_wizard_navigate_step(update, context, operator_id, step_num, engagement_id)
        return

    # eng:wz:tp:<topic_id>:<engagement_id>
    if sub == "tp" and len(parts) >= 3:
        topic_id = parts[1]
        engagement_id = parts[2]
        await _handle_wizard_pick_topic(update, context, operator_id, topic_id, engagement_id)
        return

    # eng:wz:ap:<account_id>:<engagement_id>
    if sub == "ap" and len(parts) >= 3:
        account_id = parts[1]
        engagement_id = parts[2]
        await _handle_wizard_account_pick(update, context, operator_id, account_id, engagement_id)
        return

    # eng:wz:lv:<mode>:<engagement_id>
    if sub == "lv" and len(parts) >= 3:
        level = parts[1]
        engagement_id = parts[2]
        await _handle_wizard_level(update, context, operator_id, level, engagement_id)
        return

    # eng:wz:confirm:<engagement_id>
    if sub == "confirm" and len(parts) >= 2:
        engagement_id = parts[1]
        await _handle_wizard_confirm(update, context, operator_id, engagement_id)
        return

    # eng:wz:retry:<engagement_id>
    if sub == "retry" and len(parts) >= 2:
        engagement_id = parts[1]
        await _handle_wizard_retry(update, context, operator_id, engagement_id)
        return

    # eng:wz:cancel:<engagement_id>
    if sub == "cancel" and len(parts) >= 2:
        engagement_id = parts[1]
        await _handle_wizard_cancel_prompt(update, context, operator_id, engagement_id)
        return

    # eng:wz:cancel_yes:<engagement_id>
    if sub == "cancel_yes" and len(parts) >= 2:
        _config_edit_store(context).cancel(operator_id)
        await _edit_callback_message(update, "Wizard cancelled. Use /add_engagement_target to start again.")
        return

    await _callback_reply(update, "Unknown wizard action.")


# ---------------------------------------------------------------------------
# Navigate by step number
# ---------------------------------------------------------------------------


async def _handle_wizard_navigate_step(
    update: Any,
    context: Any,
    operator_id: int,
    step_num: str,
    engagement_id: str,
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
        topic_id = _wizard_state_topic_id(state)
        if not topic_id:
            await _callback_reply(update, "Pick a topic first.")
            return
        await _show_wizard_step3(update, context, state)
    elif n == "4":
        await _show_wizard_step4(update, context, state)
    elif n == "5":
        await _show_wizard_step5(update, context, state)
    else:
        await _show_wizard_step1(update, context)


# ---------------------------------------------------------------------------
# Pick topic (single-select) and PATCH engagement
# ---------------------------------------------------------------------------


async def _handle_wizard_pick_topic(
    update: Any,
    context: Any,
    operator_id: int,
    topic_id: str,
    engagement_id: str,
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Wizard session expired. Use /add_engagement_target to start again.")
        return
    state = _wizard_state(pending)

    # Toggle: if already selected → deselect; else select
    current_topic = _wizard_state_topic_id(state)
    if current_topic == topic_id:
        state["topic_id"] = None
        has_selection = False
    else:
        state["topic_id"] = topic_id
        has_selection = True

    _config_edit_store(context).set_value(
        operator_id,
        raw_value=topic_id,
        parsed_value=None,
        flow_step="topics",
        flow_state=state,
    )

    # Save to backend if a topic was selected
    if has_selection:
        client = _api_client(context)
        try:
            await client.patch_engagement(engagement_id, topic_id=topic_id)
        except BotApiError:
            pass  # Non-fatal; state already saved locally

    # Re-render the topic picker in-place
    client = _api_client(context)
    target_ref = str(state.get("target_ref") or state.get("target_id") or "")
    try:
        data = await client.list_engagement_topics()
    except BotApiError as exc:
        await _callback_reply(update, f"Couldn't load topics: {exc.message}")
        return
    topics = data.get("items") or []
    markup = engagement_wizard_topics_markup(
        topics,
        selected_id=state["topic_id"],
        engagement_id=engagement_id,
        has_selection=has_selection,
    )
    selected_id_val = state["topic_id"]
    await _edit_callback_message(
        update,
        format_wizard_topics_prompt(
            topics,
            community_ref=target_ref,
            selected_ids=[selected_id_val] if selected_id_val else [],
        ),
        reply_markup=markup,
    )


# ---------------------------------------------------------------------------
# Pick account and PUT engagement settings
# ---------------------------------------------------------------------------


async def _handle_wizard_account_pick(
    update: Any,
    context: Any,
    operator_id: int,
    account_id: str,
    engagement_id: str,
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Wizard session expired. Use /add_engagement_target to start again.")
        return
    state = _wizard_state(pending)
    state["account_id"] = account_id
    _config_edit_store(context).set_value(
        operator_id,
        raw_value=account_id,
        parsed_value=None,
        flow_step="account",
        flow_state=state,
    )

    # Save to backend
    client = _api_client(context)
    try:
        await client.put_engagement_settings(engagement_id, assigned_account_id=account_id)
    except BotApiError as exc:
        await _reply(update, f"Couldn't assign account: {exc.message}")
        # Non-fatal: continue wizard

    # Check if we're in edit-reentry
    return_callback = state.get("return_callback")
    if return_callback:
        state["return_callback"] = None
        _config_edit_store(context).set_value(
            operator_id,
            raw_value=account_id,
            parsed_value=None,
            flow_step="review",
            flow_state=state,
        )
        await _show_wizard_step5(update, context, state)
        return

    await _show_wizard_step4(update, context, state)


async def _wizard_pick_account(
    update: Any,
    context: Any,
    account_id: str,
    state: dict[str, Any],
) -> None:
    """Auto-pick a single available account (no user interaction)."""
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return
    engagement_id = _wizard_state_engagement_id(state)
    await _handle_wizard_account_pick(update, context, operator_id, account_id, engagement_id)


# ---------------------------------------------------------------------------
# Pick mode and PUT engagement settings
# ---------------------------------------------------------------------------


async def _handle_wizard_level(
    update: Any,
    context: Any,
    operator_id: int,
    level: str,
    engagement_id: str,
) -> None:
    if level not in _WIZARD_LEVEL_MODE:
        await _callback_reply(update, f"Unknown level: {level}.")
        return
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Wizard session expired. Use /add_engagement_target to start again.")
        return
    state = _wizard_state(pending)
    state["mode"] = level
    _config_edit_store(context).set_value(
        operator_id,
        raw_value=level,
        parsed_value=None,
        flow_step="mode",
        flow_state=state,
    )

    mode = _WIZARD_LEVEL_MODE[level]
    client = _api_client(context)
    try:
        await client.put_engagement_settings(engagement_id, mode=mode)
    except BotApiError as exc:
        await _callback_reply(update, f"Couldn't save mode: {exc.message}")
        return

    # Check if we're in edit-reentry
    return_callback = state.get("return_callback")
    if return_callback:
        state["return_callback"] = None
        _config_edit_store(context).set_value(
            operator_id,
            raw_value=level,
            parsed_value=None,
            flow_step="review",
            flow_state=state,
        )
        await _show_wizard_step5(update, context, state)
        return

    await _show_wizard_step5(update, context, state)


# ---------------------------------------------------------------------------
# Edit reentry: jump to a specific step with return_callback set
# ---------------------------------------------------------------------------


async def _handle_wizard_edit_reentry(
    update: Any,
    context: Any,
    operator_id: int,
    engagement_id: str,
    field: str,
) -> None:
    editable = editable_field("wizard", "state")
    if editable is None:
        await _callback_reply(update, "Wizard is not available right now.")
        return

    # Try to get existing wizard state for this user/engagement
    pending = _config_edit_store(context).get(operator_id)
    if pending and pending.entity == "wizard":
        state = _wizard_state(pending)
        if _wizard_state_engagement_id(state) == engagement_id:
            # Already in wizard for this engagement — just jump to the step
            state["return_callback"] = f"eng:wz:step:5:{engagement_id}"
            _config_edit_store(context).set_value(
                operator_id,
                raw_value="",
                parsed_value=None,
                flow_step=field,
                flow_state=state,
            )
            if field == "topic":
                await _show_wizard_step2(update, context, state)
            elif field == "account":
                await _show_wizard_step3(update, context, state)
            elif field == "mode":
                await _show_wizard_step4(update, context, state)
            else:
                await _show_wizard_step5(update, context, state)
            return

    # Start a new wizard session for editing existing engagement
    state = {
        "engagement_id": engagement_id,
        "target_id": None,
        "target_ref": engagement_id,  # placeholder until we can fetch
        "topic_id": None,
        "account_id": None,
        "mode": None,
        "return_callback": f"eng:wz:step:5:{engagement_id}",
    }
    _config_edit_store(context).start(
        operator_id=operator_id,
        field=editable,
        object_id=engagement_id,
        flow_step=field,
        flow_state=state,
    )
    if field == "topic":
        await _show_wizard_step2(update, context, state)
    elif field == "account":
        await _show_wizard_step3(update, context, state)
    elif field == "mode":
        await _show_wizard_step4(update, context, state)
    else:
        await _show_wizard_step5(update, context, state)


# ---------------------------------------------------------------------------
# Confirm (Step 5 → wizard-confirm endpoint)
# ---------------------------------------------------------------------------


async def _handle_wizard_confirm(
    update: Any,
    context: Any,
    operator_id: int,
    engagement_id: str,
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Wizard session expired. Use /add_engagement_target to start again.")
        return

    client = _api_client(context)
    reviewer = _reviewer_label(update)
    try:
        result = await client.wizard_confirm_engagement(
            engagement_id,
            requested_by=reviewer,
        )
    except BotApiError as exc:
        await _edit_callback_message(
            update,
            f"Couldn't confirm engagement: {exc.message}\n\nUse Retry to try again.",
            reply_markup=engagement_wizard_retry_markup(engagement_id),
        )
        return

    status = str(result.get("result") or result.get("status") or "")

    if status == "confirmed":
        _config_edit_store(context).cancel(operator_id)
        await _edit_callback_message(
            update,
            "🎉 Engagement started ✓ — first results will appear in the cockpit shortly. Use /engagement to view.",
        )
        return

    if status in ("validation_failed", "blocked"):
        field = result.get("field") or ""
        message = str(result.get("message") or "Validation failed.")
        await _edit_callback_message(
            update,
            f"⚠ {message}\n\nFix the issue and try again.",
            reply_markup=engagement_wizard_retry_markup(engagement_id),
        )
        return

    if status == "stale":
        message = str(result.get("message") or "The engagement data is out of date.")
        await _edit_callback_message(
            update,
            f"⚠ {message}\n\nRetry to refresh.",
            reply_markup=engagement_wizard_retry_markup(engagement_id),
        )
        return

    # Fallback
    await _edit_callback_message(
        update,
        f"Unexpected response: {status}.\n\nUse Retry or /add_engagement_target.",
        reply_markup=engagement_wizard_retry_markup(engagement_id),
    )


# ---------------------------------------------------------------------------
# Retry (restart from Step 1)
# ---------------------------------------------------------------------------


async def _handle_wizard_retry(
    update: Any,
    context: Any,
    operator_id: int,
    engagement_id: str,
) -> None:
    client = _api_client(context)
    try:
        await client.wizard_retry_engagement(engagement_id)
    except BotApiError as exc:
        await _callback_reply(update, f"Retry failed: {exc.message}")
        return

    # Reset wizard state
    editable = editable_field("wizard", "state")
    if editable is None:
        await _callback_reply(update, "Wizard is not available right now.")
        return
    _config_edit_store(context).start(
        operator_id=operator_id,
        field=editable,
        object_id="new",
        flow_step="target",
        flow_state=_fresh_wizard_state(),
    )
    await _show_wizard_step1(update, context)


# ---------------------------------------------------------------------------
# Cancel prompt
# ---------------------------------------------------------------------------


async def _handle_wizard_cancel_prompt(
    update: Any,
    context: Any,
    operator_id: int,
    engagement_id: str,
) -> None:
    await _edit_callback_message(
        update,
        "Cancel this engagement wizard? No data will be deleted.",
        reply_markup=engagement_wizard_cancel_confirm_markup(engagement_id),
    )


# ---------------------------------------------------------------------------
# Wizard return store — kept for topic-create reentry compatibility
# ---------------------------------------------------------------------------


def _wizard_return_save(context: Any, operator_id: int, state: dict[str, Any]) -> None:
    store = context.application.bot_data.setdefault(WIZARD_RETURN_STORE_KEY, {})
    store[operator_id] = dict(state)


def _wizard_return_pop(context: Any, operator_id: int) -> dict[str, Any] | None:
    store = context.application.bot_data.get(WIZARD_RETURN_STORE_KEY) or {}
    return store.pop(operator_id, None)


async def _wizard_resume_after_topic_create(
    update: Any,
    context: Any,
    wizard_state: dict[str, Any],
    topic_data: dict[str, Any],
) -> None:
    """Re-enter the wizard after a new topic was created.

    In the new engagement-scoped flow, topics are single-select, so we just
    pre-select the newly created topic and show Step 2 again.
    """
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return

    editable = editable_field("wizard", "state")
    if editable is None:
        return

    new_topic_id = str(topic_data.get("id") or "")
    if new_topic_id:
        wizard_state["topic_id"] = new_topic_id

    # Restore wizard session
    engagement_id = wizard_state.get("engagement_id") or "new"
    _config_edit_store(context).start(
        operator_id=operator_id,
        field=editable,
        object_id=str(engagement_id),
        flow_step="topics",
        flow_state=wizard_state,
    )

    # PATCH the engagement with the new topic if we have one
    if new_topic_id and engagement_id and engagement_id != "new":
        client = _api_client(context)
        try:
            await client.patch_engagement(str(engagement_id), topic_id=new_topic_id)
        except BotApiError:
            pass

    await _show_wizard_step2(update, context, wizard_state)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


__all__ = [
    "_start_engagement_wizard",
    "_handle_wizard_callback",
    "_handle_wizard_text",
    "_wizard_resume_after_topic_create",
    "_wizard_return_pop",
]
