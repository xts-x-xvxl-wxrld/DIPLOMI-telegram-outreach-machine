from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import re
from typing import Any, Literal
from uuid import UUID

from .runtime_topic_brief_style import _topic_brief_style_target_summary


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
    flow_step: str | None = None
    flow_state: dict[str, Any] | None = None


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
        flow_step: str | None = None,
        flow_state: dict[str, Any] | None = None,
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
            flow_step=flow_step,
            flow_state=dict(flow_state or {}),
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
        flow_step: str | None = None,
        flow_state: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> PendingEdit | None:
        pending = self.get(operator_id, now=now)
        if pending is None:
            return None
        updated = replace(
            pending,
            raw_value=raw_value,
            parsed_value=parsed_value,
            flow_step=flow_step if flow_step is not None else pending.flow_step,
            flow_state=dict(flow_state) if flow_state is not None else pending.flow_state,
        )
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
    ("prompt_profile_create", "payload"): EditableField(
        entity="prompt_profile_create",
        field="payload",
        label="Prompt profile creation details",
        value_type="long_text",
        api_method="create_engagement_prompt_profile",
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
    ("topic_create", "payload"): EditableField(
        entity="topic_create",
        field="payload",
        label="Topic creation details",
        value_type="long_text",
        api_method="create_engagement_topic",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("topic_example", "good"): EditableField(
        entity="topic_example",
        field="good",
        label="Good topic example",
        value_type="long_text",
        api_method="add_engagement_topic_example",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("topic_example", "bad"): EditableField(
        entity="topic_example",
        field="bad",
        label="Bad topic example (avoid-copy guidance)",
        value_type="long_text",
        api_method="add_engagement_topic_example",
        requires_confirmation=True,
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
    ("style_rule_create", "payload"): EditableField(
        entity="style_rule_create",
        field="payload",
        label="Style rule creation details",
        value_type="long_text",
        api_method="create_engagement_style_rule",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("target_create", "payload"): EditableField(
        entity="target_create",
        field="payload",
        label="Target creation details",
        value_type="long_text",
        api_method="create_engagement_target",
        requires_confirmation=True,
        admin_only=True,
    ),
    ("wizard", "state"): EditableField(
        entity="wizard",
        field="state",
        label="Engagement wizard",
        value_type="text",
        api_method="",
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

ALLOWED_PROMPT_TEMPLATE_VARIABLES = {
    "community.title",
    "community.username",
    "community.description",
    "topic.name",
    "topic.description",
    "topic.stance_guidance",
    "topic.trigger_keywords",
    "topic.negative_keywords",
    "topic.example_good_replies",
    "topic.example_bad_replies",
    "style.global",
    "style.account",
    "style.community",
    "style.topic",
    "source_post.text",
    "source_post.tg_message_id",
    "source_post.message_date",
    "reply_context",
    "messages",
    "community_context.latest_summary",
    "community_context.dominant_themes",
}
_PROMPT_VARIABLE_RE = re.compile(r"{{\s*([a-zA-Z0-9_.]+)\s*}}")


def editable_field(entity: str, field: str) -> EditableField | None:
    return EDITABLE_FIELDS.get((entity, field))


def parse_edit_value(field: EditableField | PendingEdit, raw_value: str) -> tuple[bool, Any | str]:
    value = raw_value.strip()
    if field.value_type in {"text", "long_text"}:
        if not value:
            return False, f"{field.label} cannot be blank."
        if field.entity == "prompt_profile" and field.field == "user_prompt_template":
            invalid_variables = sorted(
                {
                    match.group(1)
                    for match in _PROMPT_VARIABLE_RE.finditer(value)
                    if match.group(1) not in ALLOWED_PROMPT_TEMPLATE_VARIABLES
                }
            )
            if invalid_variables:
                return False, "Unsupported prompt variable: " + ", ".join(invalid_variables)
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
    if pending.entity == "topic_create":
        return _render_topic_create_request(pending)
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
    if pending.entity == "topic_create" and isinstance(pending.parsed_value, dict):
        return _render_topic_create_preview(pending)
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


_TOPIC_CREATE_STEP_DETAILS: dict[str, tuple[str, str, str | None, bool]] = {
    "name": (
        "Step 1 of 7: Topic name",
        "Send the topic name as your next message.",
        "Founder outreach",
        False,
    ),
    "description": (
        "Step 2 of 7: Conversation target",
        "What kind of discussion should we notice?",
        "People comparing CRM tools or asking about migration tradeoffs.",
        False,
    ),
    "stance_guidance": (
        "Step 3 of 7: Reply position",
        "What should our reply contribute?",
        "Be practical, factual, and non-salesy.",
        False,
    ),
    "style_guidance": (
        "Step 4 of 7: Voice and style",
        "How should this account sound here?\n\nUse this for tone, brevity, disclosure, and link posture. Hard safety rules still apply.",
        "Brief, transparent, helpful, no links unless asked.",
        True,
    ),
    "example_good_replies": (
        "Step 5 of 7: Good reply examples",
        "Paste one or more replies you would be happy for the model to write. Separate multiple examples with a blank line.\n\nGood examples teach the shape of a helpful reply. The model should not copy examples word for word.",
        "Compare data ownership and export access first.",
        True,
    ),
    "example_bad_replies": (
        "Step 6 of 7: Bad reply examples",
        "Paste one or more replies that are too salesy, risky, fake, or off-tone. Separate multiple examples with a blank line.\n\nBad examples teach what to avoid. They stay negative examples only, and the model should not copy them word for word either.",
        "Buy our tool now.",
        True,
    ),
    "avoid_rules": (
        "Step 7 of 7: Avoid rules",
        "Anything the reply must never do?\n\nUse this to tighten behavior, not to weaken the hard safety rules.",
        "No DMs, no fake customer claims, no urgency.",
        True,
    ),
}
_TOPIC_CREATE_REVIEW_STEP_DETAILS: dict[str, tuple[str, str, str]] = {
    "example_good_replies_review": (
        "example_good_replies",
        "Current good examples:",
        "Add another to keep building this set, or continue when you're ready for bad examples.",
    ),
    "example_bad_replies_review": (
        "example_bad_replies",
        "Current bad examples:",
        "Add another to keep building this set, or use Done reviewing examples when you're ready for avoid rules.",
    ),
}


def _render_topic_create_request(pending: PendingEdit) -> str:
    step = pending.flow_step or "name"
    normalized_step = _topic_create_normalized_step(step)
    title, prompt, example, optional = _TOPIC_CREATE_STEP_DETAILS.get(
        normalized_step,
        _TOPIC_CREATE_STEP_DETAILS["name"],
    )
    if step in _TOPIC_CREATE_REVIEW_STEP_DETAILS:
        field_name, example_title, helper_text = _TOPIC_CREATE_REVIEW_STEP_DETAILS[step]
        examples = list((pending.flow_state or {}).get(field_name) or [])
        lines = [
            "Draft instruction wizard" if pending.object_id != "new" else "Creating draft brief",
            f"Topic ID: {pending.object_id}" if pending.object_id != "new" else "Topic Create ID: new",
            "",
            title,
            example_title,
            *_topic_example_lines(examples),
            "",
            helper_text,
            "",
            "Use /cancel_edit to discard this draft.",
        ]
        return "\n".join(lines)
    lines = [
        "Draft instruction wizard" if pending.object_id != "new" else "Creating draft brief",
        f"Topic ID: {pending.object_id}" if pending.object_id != "new" else "Topic Create ID: new",
        "",
        title,
        prompt,
    ]
    if normalized_step in {"example_good_replies", "example_bad_replies"}:
        existing_examples = list((pending.flow_state or {}).get(normalized_step) or [])
        if existing_examples:
            lines.extend(
                [
                    "",
                    "Already added:",
                    *_topic_example_lines(existing_examples),
                    "",
                    "Send another example to add it, or use the button below when the list is ready.",
                ]
            )
    if example:
        lines.append(f"Example: {example}")
    if optional:
        lines.append("Reply with - to skip this field.")
    summary_lines = _topic_create_summary_lines(pending.flow_state or {}, include_optional=False)
    if summary_lines:
        lines.extend(["", "Current values:", *summary_lines])
    lines.extend(["", "Use /cancel_edit to discard this draft."])
    return "\n".join(lines)


def _render_topic_create_preview(pending: PendingEdit) -> str:
    payload = pending.parsed_value if isinstance(pending.parsed_value, dict) else {}
    lines = [
        "Review Draft brief",
        f"Topic ID: {pending.object_id}" if pending.object_id != "new" else "Topic Create ID: new",
        "Confirmation required before saving.",
        "",
        *_topic_create_summary_lines(payload, include_optional=True),
        "",
        "Good examples teach shape, not literal templates.",
        "Bad examples stay in avoid-only guidance and are never copied into replies.",
        "Preview and save still run through the normal safety checks.",
    ]
    return "\n".join(lines)


def _topic_create_summary_lines(
    payload: dict[str, Any],
    *,
    include_optional: bool,
) -> list[str]:
    lines: list[str] = []
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    guidance = str(payload.get("stance_guidance") or "").strip()
    style_guidance = str(payload.get("style_guidance") or "").strip()
    good_examples = payload.get("example_good_replies") or []
    bad_examples = payload.get("example_bad_replies") or []
    avoid_rules = str(payload.get("avoid_rules") or "").strip()

    if name:
        lines.append(f"Name: {_shorten(name, 240)}")
    if description:
        lines.append(f"We will look for: {_shorten(description, 240)}")
    if guidance:
        lines.append(f"We will contribute: {_shorten(guidance, 240)}")
    if include_optional:
        lines.append("Voice: " + (_shorten(style_guidance, 240) if style_guidance else "-"))
        lines.append(
            "Good examples: "
            + (" | ".join(_shorten(str(example), 120) for example in good_examples) if good_examples else "-")
        )
        lines.append(
            "Bad examples: "
            + (" | ".join(_shorten(str(example), 120) for example in bad_examples) if bad_examples else "-")
        )
        lines.append("Avoid: " + (_shorten(avoid_rules, 240) if avoid_rules else "-"))
        style_target = _topic_brief_style_target_summary(payload)
        if style_target:
            lines.append("Guidance saves to: " + _shorten(style_target, 240))
    return lines


def _topic_create_normalized_step(step: str) -> str:
    if step in _TOPIC_CREATE_REVIEW_STEP_DETAILS:
        return _TOPIC_CREATE_REVIEW_STEP_DETAILS[step][0]
    return step


def _topic_example_lines(examples: list[str]) -> list[str]:
    if not examples:
        return ["- None yet"]
    return [f"{index}. {_shorten(str(example), 240)}" for index, example in enumerate(examples, start=1)]
