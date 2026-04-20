from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID


ConfigEditValueType = Literal[
    "text",
    "long_text",
    "int",
    "float",
    "bool",
    "enum",
    "time",
    "uuid",
    "keyword_list",
]


@dataclass(frozen=True)
class EditableField:
    entity: str
    field: str
    label: str
    value_type: ConfigEditValueType
    api_method: str
    requires_confirmation: bool = False
    admin_only: bool = False
    enum_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class PendingEdit:
    operator_id: int
    entity: str
    object_id: str
    field: str
    label: str
    value_type: ConfigEditValueType
    api_method: str
    requires_confirmation: bool
    admin_only: bool
    started_at: datetime
    raw_value: str | None = None
    parsed_value: Any | None = None
    enum_values: tuple[str, ...] = ()


class PendingEditStore:
    def __init__(self, *, timeout_seconds: int = 15 * 60) -> None:
        self.timeout = timedelta(seconds=timeout_seconds)
        self._edits: dict[int, PendingEdit] = {}

    def start(
        self,
        *,
        operator_id: int,
        field: EditableField,
        object_id: str,
        now: datetime | None = None,
    ) -> PendingEdit:
        pending = PendingEdit(
            operator_id=operator_id,
            entity=field.entity,
            object_id=object_id,
            field=field.field,
            label=field.label,
            value_type=field.value_type,
            api_method=field.api_method,
            requires_confirmation=field.requires_confirmation,
            admin_only=field.admin_only,
            enum_values=field.enum_values,
            started_at=now or datetime.now(UTC),
        )
        self._edits[operator_id] = pending
        return pending

    def get(self, operator_id: int, *, now: datetime | None = None) -> PendingEdit | None:
        pending = self._edits.get(operator_id)
        if pending is None:
            return None
        if self._is_expired(pending, now=now):
            self._edits.pop(operator_id, None)
            return None
        return pending

    def set_value(
        self,
        operator_id: int,
        *,
        raw_value: str,
        parsed_value: Any,
        now: datetime | None = None,
    ) -> PendingEdit | None:
        pending = self.get(operator_id, now=now)
        if pending is None:
            return None
        updated = replace(pending, raw_value=raw_value, parsed_value=parsed_value)
        self._edits[operator_id] = updated
        return updated

    def cancel(self, operator_id: int) -> PendingEdit | None:
        return self._edits.pop(operator_id, None)

    def clear_expired(self, *, now: datetime | None = None) -> None:
        for operator_id, pending in list(self._edits.items()):
            if self._is_expired(pending, now=now):
                self._edits.pop(operator_id, None)

    def _is_expired(self, pending: PendingEdit, *, now: datetime | None = None) -> bool:
        checked_at = now or datetime.now(UTC)
        return checked_at - pending.started_at > self.timeout


EDITABLE_FIELDS: dict[tuple[str, str], EditableField] = {
    ("candidate", "final_reply"): EditableField(
        entity="candidate",
        field="final_reply",
        label="Final reply",
        value_type="long_text",
        api_method="edit_engagement_candidate",
        requires_confirmation=True,
    ),
    ("target", "notes"): EditableField(
        entity="target",
        field="notes",
        label="Target notes",
        value_type="long_text",
        api_method="update_engagement_target",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("prompt_profile", "name"): EditableField(
        entity="prompt_profile",
        field="name",
        label="Prompt profile name",
        value_type="text",
        api_method="update_engagement_prompt_profile",
        admin_only=True,
    ),
    ("prompt_profile", "description"): EditableField(
        entity="prompt_profile",
        field="description",
        label="Prompt profile description",
        value_type="long_text",
        api_method="update_engagement_prompt_profile",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("prompt_profile", "model"): EditableField(
        entity="prompt_profile",
        field="model",
        label="Model",
        value_type="text",
        api_method="update_engagement_prompt_profile",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("prompt_profile", "temperature"): EditableField(
        entity="prompt_profile",
        field="temperature",
        label="Temperature",
        value_type="float",
        api_method="update_engagement_prompt_profile",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("prompt_profile", "max_output_tokens"): EditableField(
        entity="prompt_profile",
        field="max_output_tokens",
        label="Max output tokens",
        value_type="int",
        api_method="update_engagement_prompt_profile",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("prompt_profile", "system_prompt"): EditableField(
        entity="prompt_profile",
        field="system_prompt",
        label="System prompt",
        value_type="long_text",
        api_method="update_engagement_prompt_profile",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("prompt_profile", "user_prompt_template"): EditableField(
        entity="prompt_profile",
        field="user_prompt_template",
        label="User prompt template",
        value_type="long_text",
        api_method="update_engagement_prompt_profile",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("topic", "stance_guidance"): EditableField(
        entity="topic",
        field="stance_guidance",
        label="Topic guidance",
        value_type="long_text",
        api_method="update_engagement_topic",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("topic", "trigger_keywords"): EditableField(
        entity="topic",
        field="trigger_keywords",
        label="Trigger keywords",
        value_type="keyword_list",
        api_method="update_engagement_topic",
        admin_only=True,
    ),
    ("topic", "negative_keywords"): EditableField(
        entity="topic",
        field="negative_keywords",
        label="Negative keywords",
        value_type="keyword_list",
        api_method="update_engagement_topic",
        admin_only=True,
    ),
    ("style_rule", "rule_text"): EditableField(
        entity="style_rule",
        field="rule_text",
        label="Style rule text",
        value_type="long_text",
        api_method="update_engagement_style_rule",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("style_rule", "priority"): EditableField(
        entity="style_rule",
        field="priority",
        label="Style rule priority",
        value_type="int",
        api_method="update_engagement_style_rule",
        admin_only=True,
    ),
    ("style_rule", "active"): EditableField(
        entity="style_rule",
        field="active",
        label="Style rule active state",
        value_type="bool",
        api_method="update_engagement_style_rule",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("settings", "max_posts_per_day"): EditableField(
        entity="settings",
        field="max_posts_per_day",
        label="Max posts per day",
        value_type="int",
        api_method="update_engagement_settings",
        admin_only=True,
    ),
    ("settings", "min_minutes_between_posts"): EditableField(
        entity="settings",
        field="min_minutes_between_posts",
        label="Minimum minutes between posts",
        value_type="int",
        api_method="update_engagement_settings",
        admin_only=True,
    ),
    ("settings", "quiet_hours_start"): EditableField(
        entity="settings",
        field="quiet_hours_start",
        label="Quiet hours start",
        value_type="time",
        api_method="update_engagement_settings",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("settings", "quiet_hours_end"): EditableField(
        entity="settings",
        field="quiet_hours_end",
        label="Quiet hours end",
        value_type="time",
        api_method="update_engagement_settings",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("settings", "assigned_account_id"): EditableField(
        entity="settings",
        field="assigned_account_id",
        label="Assigned engagement account",
        value_type="uuid",
        api_method="update_engagement_settings",
        requires_confirmation=True,
        admin_only=True,
    ),
}


def editable_field(entity: str, field: str) -> EditableField | None:
    return EDITABLE_FIELDS.get((entity, field))


def parse_edit_value(field: EditableField | PendingEdit, raw_value: str) -> tuple[bool, Any | str]:
    value = raw_value.strip()
    if field.value_type in {"text", "long_text"}:
        if not value:
            return False, f"{field.label} cannot be blank."
        return True, value

    if field.value_type == "int":
        try:
            parsed_int = int(value)
        except ValueError:
            return False, f"{field.label} must be a whole number."
        return True, parsed_int

    if field.value_type == "float":
        try:
            parsed_float = float(value)
        except ValueError:
            return False, f"{field.label} must be a number."
        return True, parsed_float

    if field.value_type == "bool":
        parsed_bool = _parse_bool(value)
        if parsed_bool is None:
            return False, f"{field.label} must be on/off, yes/no, true/false, or 1/0."
        return True, parsed_bool

    if field.value_type == "enum":
        normalized = value.casefold()
        allowed = tuple(option.casefold() for option in field.enum_values)
        if normalized not in allowed:
            return False, f"{field.label} must be one of: {', '.join(field.enum_values)}."
        return True, field.enum_values[allowed.index(normalized)]

    if field.value_type == "time":
        if not _is_hh_mm(value):
            return False, f"{field.label} must use HH:MM time."
        return True, value

    if field.value_type == "uuid":
        try:
            return True, str(UUID(value))
        except ValueError:
            return False, f"{field.label} must be a valid UUID."

    if field.value_type == "keyword_list":
        keywords = [part.strip() for part in value.split(",") if part.strip()]
        return True, keywords

    return False, f"{field.label} uses an unsupported edit type."


def render_edit_request(pending: PendingEdit) -> str:
    return "\n".join(
        [
            f"Editing {pending.label}",
            f"{pending.entity.replace('_', ' ').title()} ID: {pending.object_id}",
            "",
            "Send the replacement value as your next message.",
            "Use /cancel_edit to discard this edit.",
        ]
    )


def render_edit_preview(pending: PendingEdit) -> str:
    value = pending.raw_value or ""
    lines = [
        f"Review {pending.label}",
        f"{pending.entity.replace('_', ' ').title()} ID: {pending.object_id}",
        f"Field: {pending.field}",
    ]
    if pending.requires_confirmation:
        lines.append("Confirmation required before saving.")
    lines.extend(["", "New value:", _shorten(value, 2800)])
    return "\n".join(lines)


def render_edit_cancelled(pending: PendingEdit | None = None) -> str:
    if pending is None:
        return "No pending edit to cancel."
    return f"Cancelled edit for {pending.label}."


def render_edit_saved(pending: PendingEdit) -> str:
    return f"Saved {pending.label}."


def _parse_bool(value: str) -> bool | None:
    normalized = value.casefold()
    if normalized in {"on", "yes", "true", "1"}:
        return True
    if normalized in {"off", "no", "false", "0"}:
        return False
    return None


def _is_hh_mm(value: str) -> bool:
    parts = value.split(":")
    if len(parts) != 2 or any(len(part) != 2 or not part.isdigit() for part in parts):
        return False
    hour = int(parts[0])
    minute = int(parts[1])
    return 0 <= hour <= 23 and 0 <= minute <= 59


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
