from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bot.config_editing import PendingEditStore, editable_field, parse_edit_value


def test_editable_field_registry_exposes_slice_four_fields() -> None:
    candidate_field = editable_field("candidate", "final_reply")
    target_field = editable_field("target", "notes")
    prompt_field = editable_field("prompt_profile", "system_prompt")
    prompt_create_field = editable_field("prompt_profile_create", "payload")
    topic_create_field = editable_field("topic_create", "payload")
    topic_example_field = editable_field("topic_example", "bad")
    style_create_field = editable_field("style_rule_create", "payload")
    target_create_field = editable_field("target_create", "payload")
    settings_field = editable_field("settings", "assigned_account_id")

    assert candidate_field is not None
    assert candidate_field.api_method == "edit_engagement_candidate"
    assert candidate_field.requires_confirmation is True
    assert target_field is not None
    assert target_field.api_method == "update_engagement_target"
    assert target_field.admin_only is True
    assert prompt_field is not None
    assert prompt_field.admin_only is True
    assert prompt_create_field is not None
    assert prompt_create_field.api_method == "create_engagement_prompt_profile"
    assert prompt_create_field.admin_only is True
    assert topic_create_field is not None
    assert topic_create_field.api_method == "create_engagement_topic"
    assert topic_example_field is not None
    assert topic_example_field.api_method == "add_engagement_topic_example"
    assert topic_example_field.requires_confirmation is True
    assert style_create_field is not None
    assert style_create_field.api_method == "create_engagement_style_rule"
    assert target_create_field is not None
    assert target_create_field.api_method == "create_engagement_target"
    assert settings_field is not None
    assert settings_field.value_type == "uuid"


def test_parse_edit_value_handles_supported_types() -> None:
    int_field = editable_field("settings", "max_posts_per_day")
    bool_field = editable_field("style_rule", "active")
    time_field = editable_field("settings", "quiet_hours_start")
    uuid_field = editable_field("settings", "assigned_account_id")
    keywords_field = editable_field("topic", "trigger_keywords")

    assert int_field is not None
    assert bool_field is not None
    assert time_field is not None
    assert uuid_field is not None
    assert keywords_field is not None

    assert parse_edit_value(int_field, "3") == (True, 3)
    assert parse_edit_value(bool_field, "off") == (True, False)
    assert parse_edit_value(time_field, "09:30") == (True, "09:30")
    assert parse_edit_value(
        uuid_field,
        "12345678-1234-1234-1234-123456789abc",
    ) == (True, "12345678-1234-1234-1234-123456789abc")
    assert parse_edit_value(keywords_field, "crm, open source, ") == (
        True,
        ["crm", "open source"],
    )


def test_parse_edit_value_rejects_malformed_values() -> None:
    int_field = editable_field("settings", "max_posts_per_day")
    time_field = editable_field("settings", "quiet_hours_start")
    uuid_field = editable_field("settings", "assigned_account_id")

    assert int_field is not None
    assert time_field is not None
    assert uuid_field is not None

    assert parse_edit_value(int_field, "many")[0] is False
    assert parse_edit_value(time_field, "25:00")[0] is False
    assert parse_edit_value(uuid_field, "account-1")[0] is False


def test_parse_edit_value_rejects_unapproved_prompt_template_variables() -> None:
    field = editable_field("prompt_profile", "user_prompt_template")
    assert field is not None

    assert parse_edit_value(field, "Source: {{source_post.text}}") == (
        True,
        "Source: {{source_post.text}}",
    )
    ok, error = parse_edit_value(field, "Sender: {{sender.username}}")

    assert ok is False
    assert "sender.username" in str(error)


def test_pending_edit_store_scopes_edits_by_operator() -> None:
    store = PendingEditStore()
    field = editable_field("candidate", "final_reply")
    assert field is not None

    first = store.start(operator_id=123, field=field, object_id="candidate-1")
    second = store.start(operator_id=456, field=field, object_id="candidate-2")

    assert store.get(123) == first
    assert store.get(456) == second
    assert store.cancel(456) == second
    assert store.get(123) == first


def test_pending_edit_store_expires_stale_edits() -> None:
    now = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
    store = PendingEditStore(timeout_seconds=60)
    field = editable_field("candidate", "final_reply")
    assert field is not None

    store.start(operator_id=123, field=field, object_id="candidate-1", now=now)

    assert store.get(123, now=now + timedelta(seconds=30)) is not None
    assert store.get(123, now=now + timedelta(seconds=61)) is None
