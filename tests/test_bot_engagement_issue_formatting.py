from __future__ import annotations

from bot.engagement_issue_flow import _parse_time_range
from bot.formatting_engagement_issue import (
    format_issue_action_result,
    format_issue_card,
    format_issue_queue,
    format_quiet_hours_saved,
    format_quiet_hours_state,
    format_rate_limit_detail,
)


def test_format_issue_queue_shows_count_and_offset() -> None:
    data = {
        "queue_count": 3,
        "empty_state": "All clear.",
        "current": {"issue_id": "x", "issue_type": "topics_not_chosen"},
    }
    text = format_issue_queue(data, offset=0, scoped=False)
    assert "3 open" in text
    assert "issue" in text.lower()


def test_format_issue_queue_empty_state() -> None:
    data = {"queue_count": 0, "empty_state": "All clear.", "current": None}
    text = format_issue_queue(data, offset=0, scoped=False)
    assert "All clear." in text


def test_format_issue_queue_scoped_empty() -> None:
    data = {"queue_count": 0, "empty_state": "No issues.", "current": None}
    text = format_issue_queue(data, offset=0, scoped=True)
    assert "No issues." in text


def test_format_issue_card_shows_type_and_context() -> None:
    item = {
        "issue_id": "issue-1",
        "engagement_id": "eng-1",
        "issue_type": "topics_not_chosen",
        "issue_label": "Topics not chosen",
        "target_label": "Open CRM · @founders",
        "context": "Choose or create a topic",
        "fix_actions": [],
    }
    text = format_issue_card(item)
    assert "Topics not chosen" in text
    assert "Open CRM" in text
    assert "Choose or create a topic" in text


def test_format_issue_card_shows_skipped_badge() -> None:
    item = {
        "issue_id": "issue-1",
        "engagement_id": "eng-1",
        "issue_type": "reply_failed",
        "issue_label": "Reply failed",
        "target_label": "Builder Slack",
        "context": "Retry the failed reply",
        "fix_actions": [],
    }
    text = format_issue_card(item, skipped=True)
    assert "skipped before" in text.lower()


def test_format_issue_card_shows_index() -> None:
    item = {
        "issue_id": "issue-1",
        "engagement_id": "eng-1",
        "issue_type": "sending_is_paused",
        "issue_label": "Sending is paused",
        "target_label": "Group A",
        "context": "Resume sending",
        "fix_actions": [],
    }
    text = format_issue_card(item, index=2)
    assert "2." in text


def test_format_rate_limit_detail_fields() -> None:
    data = {
        "result": "ok",
        "message": "Sending is paused until the limit clears.",
        "next_callback": "eng:iss:open:issue-1",
        "title": "Rate limit active",
        "target_label": "Open CRM · @founders",
        "blocked_action_label": "Send reply",
        "scope_label": "Account limit",
        "reset_at": "2026-04-28T08:00:00+00:00",
    }
    text = format_rate_limit_detail(data)
    assert "Rate limit active" in text
    assert "Account limit" in text
    assert "Send reply" in text
    assert "2026-04-28" in text


def test_format_quiet_hours_state_enabled() -> None:
    data = {
        "title": "Quiet hours",
        "target_label": "Group B",
        "quiet_hours_enabled": True,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }
    text = format_quiet_hours_state(data)
    assert "22:00" in text
    assert "08:00" in text
    assert "Enabled" in text


def test_format_quiet_hours_state_disabled() -> None:
    data = {
        "title": "Quiet hours",
        "target_label": "Group B",
        "quiet_hours_enabled": False,
        "quiet_hours_start": None,
        "quiet_hours_end": None,
    }
    text = format_quiet_hours_state(data)
    assert "Disabled" in text


def test_format_quiet_hours_saved_enabled() -> None:
    data = {
        "result": "updated",
        "quiet_hours_enabled": True,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }
    text = format_quiet_hours_saved(data)
    assert "updated" in text.lower()
    assert "22:00" in text


def test_format_issue_action_result_resolved() -> None:
    text = format_issue_action_result("resolved")
    assert "resolved" in text.lower()


def test_format_issue_action_result_noop() -> None:
    text = format_issue_action_result("noop")
    assert "no change" in text.lower()


def test_format_issue_action_result_blocked_with_reason() -> None:
    text = format_issue_action_result("blocked", message="Cannot do that right now.")
    assert "Cannot do that right now." in text


def test_format_issue_action_result_stale() -> None:
    text = format_issue_action_result("stale")
    assert "stale" in text.lower() or "resolved" in text.lower()


def test_time_range_parser_valid() -> None:
    result = _parse_time_range("22:00-08:00")
    assert result == ("22:00", "08:00")


def test_time_range_parser_single_digit_hour() -> None:
    result = _parse_time_range("8:00-22:00")
    assert result == ("08:00", "22:00")


def test_time_range_parser_invalid_returns_none() -> None:
    assert _parse_time_range("not-a-time") is None
    assert _parse_time_range("25:00-08:00") is None
    assert _parse_time_range("22:60-08:00") is None
    assert _parse_time_range("off") is None


def test_time_range_parser_with_spaces() -> None:
    result = _parse_time_range("22:00 - 08:00")
    assert result == ("22:00", "08:00")
