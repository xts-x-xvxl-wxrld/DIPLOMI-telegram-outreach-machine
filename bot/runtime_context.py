# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from datetime import UTC, datetime
import logging

from .runtime_base import *

LOGGER = logging.getLogger(__name__)


def _api_client(context: Any) -> BotApiClient:
    return context.application.bot_data[API_CLIENT_KEY]


def _config_edit_store(context: Any) -> PendingEditStore:
    store = context.application.bot_data.get(CONFIG_EDIT_STORE_KEY)
    if store is None:
        store = PendingEditStore()
        context.application.bot_data[CONFIG_EDIT_STORE_KEY] = store
    return store


def _account_confirm_store(context: Any) -> dict[int, dict[str, Any]]:
    store = context.application.bot_data.get(ACCOUNT_CONFIRM_STORE_KEY)
    if store is None:
        store = {}
        context.application.bot_data[ACCOUNT_CONFIRM_STORE_KEY] = store
    return store


def _topic_brief_draft_store(context: Any) -> dict[int, PendingEdit]:
    store = context.application.bot_data.get(TOPIC_BRIEF_DRAFT_STORE_KEY)
    if not isinstance(store, dict):
        store = {}
        context.application.bot_data[TOPIC_BRIEF_DRAFT_STORE_KEY] = store
    return store


def _remember_topic_brief_pending(context: Any, pending: PendingEdit) -> None:
    if pending.entity != "topic_create":
        return
    _topic_brief_draft_store(context)[pending.operator_id] = pending


def _forget_topic_brief_pending(context: Any, operator_id: int) -> PendingEdit | None:
    return _topic_brief_draft_store(context).pop(operator_id, None)


def _restore_topic_brief_pending(context: Any, operator_id: int) -> PendingEdit | None:
    snapshot = _topic_brief_draft_store(context).get(operator_id)
    if snapshot is None or snapshot.entity != "topic_create":
        return None
    edit_store = _config_edit_store(context)
    now = datetime.now(UTC)
    if now - snapshot.started_at > edit_store.timeout:
        _forget_topic_brief_pending(context, operator_id)
        LOGGER.info("Discarded expired topic brief snapshot operator_id=%s", operator_id)
        return None
    restored = edit_store.start(
        operator_id=operator_id,
        field=editable_field("topic_create", "payload") or EditableField(
            entity="topic_create",
            field="payload",
            label="Topic creation details",
            value_type="long_text",
            api_method="create_engagement_topic",
            requires_confirmation=True,
            admin_only=True,
        ),
        object_id=snapshot.object_id,
        flow_step=snapshot.flow_step,
        flow_state=snapshot.flow_state,
        now=snapshot.started_at,
    )
    if snapshot.raw_value is not None or snapshot.parsed_value is not None:
        restored = (
            edit_store.set_value(
                operator_id,
                raw_value=snapshot.raw_value or "",
                parsed_value=snapshot.parsed_value,
                flow_step=snapshot.flow_step,
                flow_state=snapshot.flow_state,
                now=snapshot.started_at,
            )
            or restored
        )
    LOGGER.warning(
        "Restored missing topic brief pending state operator_id=%s step=%s object_id=%s",
        operator_id,
        restored.flow_step,
        restored.object_id,
    )
    return restored


def _get_topic_brief_pending(
    context: Any,
    operator_id: int,
    *,
    restore_missing: bool = False,
) -> PendingEdit | None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is not None:
        return pending if pending.entity == "topic_create" else None
    if not restore_missing:
        return None
    return _restore_topic_brief_pending(context, operator_id)


def _bot_settings(context: Any) -> BotSettings | None:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None)
    if not isinstance(bot_data, dict):
        return None
    settings = bot_data.get("settings")
    return settings if isinstance(settings, BotSettings) else None


__all__ = [
    "_api_client",
    "_config_edit_store",
    "_account_confirm_store",
    "_topic_brief_draft_store",
    "_remember_topic_brief_pending",
    "_forget_topic_brief_pending",
    "_restore_topic_brief_pending",
    "_get_topic_brief_pending",
    "_bot_settings",
]
