from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.main import (
    API_CLIENT_KEY,
    CONFIG_EDIT_STORE_KEY,
    add_engagement_target_command,
    archive_engagement_target_command,
    callback_query,
    create_engagement_topic_command,
    detect_engagement_command,
    engagement_admin_command,
    engagement_actions_command,
    engagement_candidates_command,
    engagement_command,
    engagement_settings_command,
    engagement_target_command,
    engagement_targets_command,
    engagement_topics_command,
    edit_reply_command,
    join_community_command,
    reject_engagement_target_command,
    resolve_engagement_target_command,
    send_reply_command,
    approve_reply_command,
    target_detect_command,
    target_join_command,
    target_permission_command,
    set_engagement_command,
    toggle_engagement_topic_command,
    telegram_entity_text,
)


class _FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.replies: list[dict[str, Any]] = []

    async def reply_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.replies.append({"text": text, "reply_markup": reply_markup})


class _FakeCallbackQuery:
    def __init__(self, data: str, *, user_id: int = 123) -> None:
        self.data = data
        self.message = _FakeMessage()
        self.from_user = SimpleNamespace(id=user_id, username="operator")
        self.answers: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append({"text": text, "show_alert": show_alert})

    async def edit_message_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.edits.append({"text": text, "reply_markup": reply_markup})


class _FakeApiClient:
    def __init__(self) -> None:
        self.list_candidate_calls: list[dict[str, Any]] = []
        self.send_calls: list[dict[str, Any]] = []
        self.approve_calls: list[dict[str, Any]] = []
        self.edit_candidate_calls: list[dict[str, Any]] = []
        self.create_topic_calls: list[dict[str, Any]] = []
        self.update_topic_calls: list[dict[str, Any]] = []
        self.get_settings_calls: list[str] = []
        self.update_settings_calls: list[dict[str, Any]] = []
        self.target_list_calls: list[dict[str, Any]] = []
        self.get_target_calls: list[str] = []
        self.create_target_calls: list[dict[str, Any]] = []
        self.update_target_calls: list[dict[str, Any]] = []
        self.resolve_target_calls: list[dict[str, Any]] = []
        self.target_join_calls: list[dict[str, Any]] = []
        self.target_detect_calls: list[dict[str, Any]] = []
        self.seed_resolution_calls: list[str] = []
        self.prompt_list_calls: list[dict[str, Any]] = []
        self.style_list_calls: list[dict[str, Any]] = []
        self.join_calls: list[dict[str, Any]] = []
        self.detect_calls: list[dict[str, Any]] = []
        self.action_calls: list[dict[str, Any]] = []
        self.settings = {
            "community_id": "community-1",
            "mode": "disabled",
            "allow_join": False,
            "allow_post": False,
            "reply_only": True,
            "require_approval": True,
            "max_posts_per_day": 1,
            "min_minutes_between_posts": 240,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "assigned_account_id": None,
            "created_at": None,
            "updated_at": None,
        }
        self.actions = [
            {
                "id": "action-1",
                "community_id": "community-1",
                "candidate_id": "candidate-approved",
                "telegram_account_id": "account-1",
                "action_type": "reply",
                "status": "failed",
                "outbound_text": "Compare ownership and integrations first.",
                "reply_to_tg_message_id": 101,
                "sent_tg_message_id": None,
                "error_message": "Flood wait",
                "created_at": "2026-04-19T10:00:00Z",
                "sent_at": None,
            },
            {
                "id": "action-2",
                "community_id": "community-2",
                "candidate_id": None,
                "telegram_account_id": "account-1",
                "action_type": "join",
                "status": "sent",
                "outbound_text": None,
                "created_at": "2026-04-19T11:00:00Z",
                "sent_at": "2026-04-19T11:01:00Z",
            },
        ]
        self.topics = [
            {
                "id": "topic-1",
                "name": "Open CRM",
                "stance_guidance": "Be factual, brief, and non-salesy.",
                "trigger_keywords": ["crm", "open source"],
                "negative_keywords": [],
                "active": True,
            },
            {
                "id": "topic-2",
                "name": "Automation",
                "stance_guidance": "Discuss practical automation tradeoffs.",
                "trigger_keywords": ["automation"],
                "negative_keywords": [],
                "active": False,
            },
        ]
        self.targets = [
            {
                "id": "target-pending",
                "submitted_ref": "username:pending",
                "submitted_ref_type": "telegram_username",
                "status": "pending",
                "community_id": None,
                "community_title": None,
                "allow_join": False,
                "allow_detect": False,
                "allow_post": False,
                "added_by": "telegram:123",
                "created_at": "2026-04-19T10:00:00Z",
                "updated_at": "2026-04-19T10:00:00Z",
            },
            {
                "id": "target-approved",
                "submitted_ref": "username:founders",
                "submitted_ref_type": "telegram_username",
                "status": "approved",
                "community_id": "community-1",
                "community_title": "Founder Circle",
                "allow_join": True,
                "allow_detect": True,
                "allow_post": False,
                "added_by": "telegram:123",
                "created_at": "2026-04-19T10:00:00Z",
                "updated_at": "2026-04-19T10:00:00Z",
            },
            {
                "id": "target-resolved",
                "submitted_ref": "username:resolved",
                "submitted_ref_type": "telegram_username",
                "status": "resolved",
                "community_id": "community-2",
                "community_title": "Resolved Circle",
                "allow_join": False,
                "allow_detect": False,
                "allow_post": False,
                "added_by": "telegram:123",
                "created_at": "2026-04-19T10:00:00Z",
                "updated_at": "2026-04-19T10:00:00Z",
            },
        ]
        self.candidates_by_status = {
            "needs_review": {
                "items": [
                    {
                        "id": "candidate-review",
                        "community_title": "Founder Circle",
                        "topic_name": "Open CRM",
                        "status": "needs_review",
                        "source_excerpt": "Discussing CRM tools.",
                        "detected_reason": "Relevant CRM discussion.",
                        "suggested_reply": "Compare ownership and integrations first.",
                    }
                ],
                "total": 1,
            },
            "approved": {
                "items": [
                    {
                        "id": "candidate-approved",
                        "community_title": "Founder Circle",
                        "topic_name": "Open CRM",
                        "status": "approved",
                        "source_excerpt": "Discussing CRM tools.",
                        "detected_reason": "Relevant CRM discussion.",
                        "suggested_reply": "Compare ownership and integrations first.",
                    }
                ],
                "total": 1,
            },
            "failed": {"items": [], "total": 3},
        }

    async def list_engagement_targets(
        self,
        *,
        status: str | None = None,
        limit: int = 5,
        offset: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        self.target_list_calls.append({"status": status, "limit": limit, "offset": offset})
        items = [
            target
            for target in self.targets
            if status is None or target["status"] == status
        ]
        return {
            "items": items[offset : offset + limit],
            "total": len(items),
            "limit": limit,
            "offset": offset,
        }

    async def get_engagement_target(self, target_id: str) -> dict[str, Any]:
        self.get_target_calls.append(target_id)
        target = next((item for item in self.targets if item["id"] == target_id), None)
        return dict(target or {**self.targets[0], "id": target_id})

    async def create_engagement_target(
        self,
        *,
        target_ref: str,
        added_by: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        self.create_target_calls.append(
            {"target_ref": target_ref, "added_by": added_by, "notes": notes}
        )
        return {
            **self.targets[0],
            "id": "target-created",
            "submitted_ref": f"username:{target_ref.lstrip('@')}",
        }

    async def update_engagement_target(self, target_id: str, **updates: Any) -> dict[str, Any]:
        self.update_target_calls.append({"target_id": target_id, "updates": updates})
        target = await self.get_engagement_target(target_id)
        updated = {**target, **{key: value for key, value in updates.items() if key != "updated_by"}}
        if updated["status"] in {"rejected", "archived"}:
            updated["allow_join"] = False
            updated["allow_detect"] = False
            updated["allow_post"] = False
        self.targets = [updated if item["id"] == target_id else item for item in self.targets]
        return updated

    async def resolve_engagement_target(
        self,
        target_id: str,
        *,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        self.resolve_target_calls.append({"target_id": target_id, "requested_by": requested_by})
        return {"job": {"id": "target-resolve-job", "type": "engagement_target.resolve", "status": "queued"}}

    async def start_engagement_target_join(
        self,
        target_id: str,
        *,
        requested_by: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        self.target_join_calls.append({"target_id": target_id, "requested_by": requested_by})
        return {"job": {"id": "target-join-job", "type": "community.join", "status": "queued"}}

    async def start_engagement_target_detection(
        self,
        target_id: str,
        *,
        window_minutes: int = 60,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        self.target_detect_calls.append(
            {
                "target_id": target_id,
                "window_minutes": window_minutes,
                "requested_by": requested_by,
            }
        )
        return {"job": {"id": "target-detect-job", "type": "engagement.detect", "status": "queued"}}

    async def start_seed_group_resolution(self, seed_group_id: str, **_: Any) -> dict[str, Any]:
        self.seed_resolution_calls.append(seed_group_id)
        return {"job": {"id": "seed-job", "type": "seed.resolve", "status": "queued"}}

    async def list_engagement_prompt_profiles(
        self,
        *,
        limit: int = 5,
        offset: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        self.prompt_list_calls.append({"limit": limit, "offset": offset})
        return {"items": [], "total": 1, "limit": limit, "offset": offset}

    async def list_engagement_style_rules(
        self,
        *,
        limit: int = 5,
        offset: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        self.style_list_calls.append({"limit": limit, "offset": offset})
        return {"items": [], "total": 4, "limit": limit, "offset": offset}

    async def list_engagement_candidates(
        self,
        *,
        status: str = "needs_review",
        limit: int = 5,
        offset: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        self.list_candidate_calls.append({"status": status, "limit": limit, "offset": offset})
        page = self.candidates_by_status.get(status, {"items": [], "total": 0})
        return {"items": page["items"], "total": page["total"], "limit": limit, "offset": offset}

    async def list_engagement_topics(self) -> dict[str, Any]:
        return {"items": self.topics, "total": len(self.topics)}

    async def create_engagement_topic(
        self,
        *,
        name: str,
        stance_guidance: str,
        trigger_keywords: list[str],
        active: bool = True,
        **_: Any,
    ) -> dict[str, Any]:
        self.create_topic_calls.append(
            {
                "name": name,
                "stance_guidance": stance_guidance,
                "trigger_keywords": trigger_keywords,
                "active": active,
            }
        )
        return {
            "id": "topic-created",
            "name": name,
            "stance_guidance": stance_guidance,
            "trigger_keywords": trigger_keywords,
            "negative_keywords": [],
            "active": active,
        }

    async def update_engagement_topic(self, topic_id: str, **updates: Any) -> dict[str, Any]:
        self.update_topic_calls.append({"topic_id": topic_id, "updates": updates})
        topic = next((item for item in self.topics if item["id"] == topic_id), None)
        if topic is None:
            topic = {
                "id": topic_id,
                "name": "Topic",
                "stance_guidance": "Be useful.",
                "trigger_keywords": ["topic"],
                "negative_keywords": [],
                "active": True,
            }
        updated = {**topic, **updates}
        return updated

    async def get_engagement_settings(self, community_id: str) -> dict[str, Any]:
        self.get_settings_calls.append(community_id)
        return {**self.settings, "community_id": community_id}

    async def update_engagement_settings(self, community_id: str, **updates: Any) -> dict[str, Any]:
        self.update_settings_calls.append({"community_id": community_id, "updates": updates})
        self.settings = {**self.settings, **updates, "community_id": community_id}
        return self.settings

    async def start_community_join(
        self,
        community_id: str,
        *,
        requested_by: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        self.join_calls.append({"community_id": community_id, "requested_by": requested_by})
        return {"job": {"id": "join-job", "type": "community.join", "status": "queued"}}

    async def start_engagement_detection(
        self,
        community_id: str,
        *,
        window_minutes: int = 60,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        self.detect_calls.append(
            {
                "community_id": community_id,
                "window_minutes": window_minutes,
                "requested_by": requested_by,
            }
        )
        return {"job": {"id": "detect-job", "type": "engagement.detect", "status": "queued"}}

    async def list_engagement_actions(
        self,
        *,
        community_id: str | None = None,
        limit: int = 5,
        offset: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        self.action_calls.append({"community_id": community_id, "limit": limit, "offset": offset})
        items = [
            action
            for action in self.actions
            if community_id is None or action["community_id"] == community_id
        ]
        return {
            "items": items[offset : offset + limit],
            "total": len(items),
            "limit": limit,
            "offset": offset,
        }

    async def approve_engagement_candidate(
        self,
        candidate_id: str,
        *,
        reviewed_by: str,
    ) -> dict[str, Any]:
        self.approve_calls.append({"candidate_id": candidate_id, "reviewed_by": reviewed_by})
        return {
            "id": candidate_id,
            "community_title": "Founder Circle",
            "status": "approved",
            "reviewed_by": reviewed_by,
        }

    async def send_engagement_candidate(
        self,
        candidate_id: str,
        *,
        approved_by: str | None,
    ) -> dict[str, Any]:
        self.send_calls.append({"candidate_id": candidate_id, "approved_by": approved_by})
        return {"job": {"id": "send-job", "type": "engagement.send", "status": "queued"}}

    async def edit_engagement_candidate(
        self,
        candidate_id: str,
        *,
        final_reply: str,
        edited_by: str,
        edit_reason: str | None = None,
    ) -> dict[str, Any]:
        self.edit_candidate_calls.append(
            {
                "candidate_id": candidate_id,
                "final_reply": final_reply,
                "edited_by": edited_by,
                "edit_reason": edit_reason,
            }
        )
        return {
            "id": candidate_id,
            "community_title": "Founder Circle",
            "topic_name": "Open CRM",
            "status": "needs_review",
            "source_excerpt": "Discussing CRM tools.",
            "detected_reason": "Relevant CRM discussion.",
            "suggested_reply": "Compare ownership and integrations first.",
            "final_reply": final_reply,
        }


def _context(client: _FakeApiClient, *args: str) -> SimpleNamespace:
    return SimpleNamespace(
        args=list(args),
        application=SimpleNamespace(bot_data={API_CLIENT_KEY: client}),
    )


def _message_update(text: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        message=_FakeMessage(text=text),
        callback_query=None,
        effective_user=SimpleNamespace(id=123, username="operator"),
    )


def _callback_update(data: str, *, user_id: int = 123) -> SimpleNamespace:
    query = _FakeCallbackQuery(data, user_id=user_id)
    return SimpleNamespace(
        message=None,
        callback_query=query,
        effective_user=query.from_user,
    )


def _callback_data_values(markup: Any | None) -> list[str]:
    if markup is None:
        return []
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if getattr(button, "callback_data", None)
    ]


def _button_labels(markup: Any | None) -> list[str]:
    if markup is None:
        return []
    return [
        button.text
        for row in markup.inline_keyboard
        for button in row
        if getattr(button, "text", None)
    ]


@pytest.mark.asyncio
async def test_engagement_command_builds_home_counts_from_api_client() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_command(update, _context(client))

    assert "Review replies: 1" in update.message.replies[0]["text"]
    assert "Approved to send: 1" in update.message.replies[0]["text"]
    assert "Needs attention: 3" in update.message.replies[0]["text"]
    assert "Active topics: 1" in update.message.replies[0]["text"]
    labels = _button_labels(update.message.replies[0]["reply_markup"])
    for label in [
        "Today",
        "Review replies",
        "Approved to send",
        "Communities",
        "Topics",
        "Recent actions",
        "Admin",
        "Home",
    ]:
        assert label in labels
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:cand:list:needs_review:0" in callbacks
    assert "eng:cand:list:approved:0" in callbacks
    assert "eng:admin:tgt:0" in callbacks
    assert [call["status"] for call in client.list_candidate_calls] == [
        "needs_review",
        "approved",
        "failed",
    ]


@pytest.mark.asyncio
async def test_engagement_admin_command_uses_setup_navigation() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_admin_command(update, _context(client))

    assert "Communities: 3" in update.message.replies[0]["text"]
    assert "Topics: 2" in update.message.replies[0]["text"]
    assert "Voice rules: 4" in update.message.replies[0]["text"]
    labels = _button_labels(update.message.replies[0]["reply_markup"])
    for label in [
        "Communities",
        "Topics",
        "Voice rules",
        "Limits/accounts",
        "Advanced",
        "Back",
        "Home",
    ]:
        assert label in labels
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:admin:lim" in callbacks
    assert "eng:admin:adv" in callbacks


@pytest.mark.asyncio
async def test_engagement_admin_limit_and_advanced_callbacks_have_destinations() -> None:
    client = _FakeApiClient()
    limits_update = _callback_update("eng:admin:lim")
    advanced_update = _callback_update("eng:admin:adv")

    await callback_query(limits_update, _context(client))
    await callback_query(advanced_update, _context(client))

    assert "Limits and accounts" in limits_update.callback_query.message.replies[0]["text"]
    assert "Settings lookup: /engagement_settings <community_id>" in (
        limits_update.callback_query.message.replies[0]["text"]
    )
    assert "Advanced engagement" in advanced_update.callback_query.message.replies[0]["text"]
    assert "Prompt profiles: /engagement_prompts" in (
        advanced_update.callback_query.message.replies[0]["text"]
    )


@pytest.mark.asyncio
async def test_engagement_targets_command_filters_and_shows_target_controls() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_targets_command(update, _context(client, "approved"))

    assert client.target_list_calls[-1] == {"status": "approved", "limit": 5, "offset": 0}
    assert "Engagement targets | approved" in update.message.replies[0]["text"]
    card = update.message.replies[1]
    assert "Readiness: Drafting replies" in card["text"]
    callbacks = _callback_data_values(card["reply_markup"])
    assert "eng:admin:to:target-approved" in callbacks
    assert "eng:admin:tp:target-approved:p:1" in callbacks
    assert "eng:admin:tj:target-approved" in callbacks
    assert "eng:admin:td:target-approved:60" in callbacks


@pytest.mark.asyncio
async def test_engagement_target_detail_command_reads_target_without_seed_api() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_target_command(update, _context(client, "target-approved"))

    assert client.get_target_calls == ["target-approved"]
    assert client.seed_resolution_calls == []
    assert "Target ID: target-approved" in update.message.replies[0]["text"]
    assert "Community ID: community-1" in update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_add_engagement_target_command_uses_target_api_only() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await add_engagement_target_command(update, _context(client, "@newgroup"))

    assert client.create_target_calls == [
        {
            "target_ref": "@newgroup",
            "added_by": "telegram:123:@operator",
            "notes": None,
        }
    ]
    assert client.seed_resolution_calls == []
    assert "Engagement target added." in update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_resolve_target_command_queues_engagement_target_job() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await resolve_engagement_target_command(update, _context(client, "target-pending"))

    assert client.resolve_target_calls == [
        {"target_id": "target-pending", "requested_by": "telegram:123:@operator"}
    ]
    assert client.seed_resolution_calls == []
    assert "Engagement target resolution queued." in update.message.replies[0]["text"]
    assert "target-resolve-job (engagement_target.resolve)" in update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_target_permission_command_displays_before_after_state() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await target_permission_command(update, _context(client, "target-approved", "post", "on"))

    assert client.update_target_calls[-1] == {
        "target_id": "target-approved",
        "updates": {"allow_post": True, "updated_by": "telegram:123:@operator"},
    }
    message = update.message.replies[0]["text"]
    assert "Before: status=approved, join=yes, detect=yes, post=no" in message
    assert "After: status=approved, join=yes, detect=yes, post=yes" in message


@pytest.mark.asyncio
async def test_reject_and_archive_target_force_permissions_off() -> None:
    client = _FakeApiClient()
    reject_update = _message_update()
    archive_update = _message_update()

    await reject_engagement_target_command(reject_update, _context(client, "target-approved"))
    client.targets[1] = {**client.targets[1], "status": "approved", "allow_post": True}
    await archive_engagement_target_command(archive_update, _context(client, "target-approved"))

    assert "After: status=rejected, join=no, detect=no, post=no" in reject_update.message.replies[0]["text"]
    assert "After: status=archived, join=no, detect=no, post=no" in archive_update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_target_join_and_detect_commands_use_target_scoped_routes() -> None:
    client = _FakeApiClient()
    join_update = _message_update()
    detect_update = _message_update()

    await target_join_command(join_update, _context(client, "target-approved"))
    await target_detect_command(detect_update, _context(client, "target-approved", "45"))

    assert client.target_join_calls == [
        {"target_id": "target-approved", "requested_by": "telegram:123:@operator"}
    ]
    assert client.target_detect_calls == [
        {
            "target_id": "target-approved",
            "window_minutes": 45,
            "requested_by": "telegram:123:@operator",
        }
    ]
    assert "Target join queued." in join_update.message.replies[0]["text"]
    assert "Target engagement detection queued." in detect_update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_target_callbacks_open_toggle_and_queue_jobs() -> None:
    client = _FakeApiClient()
    open_update = _callback_update("eng:admin:to:target-approved")
    toggle_update = _callback_update("eng:admin:tp:target-approved:p:1")
    join_update = _callback_update("eng:admin:tj:target-approved")
    detect_update = _callback_update("eng:admin:td:target-approved:60")

    await callback_query(open_update, _context(client))
    await callback_query(toggle_update, _context(client))
    await callback_query(join_update, _context(client))
    await callback_query(detect_update, _context(client))

    assert "Target ID: target-approved" in open_update.callback_query.message.replies[0]["text"]
    assert "After: status=approved" in toggle_update.callback_query.edits[0]["text"]
    assert client.target_join_calls[-1]["target_id"] == "target-approved"
    assert client.target_detect_calls[-1]["window_minutes"] == 60


@pytest.mark.asyncio
async def test_engagement_settings_command_shows_disabled_synthetic_settings() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_settings_command(update, _context(client, "community-1"))

    assert client.get_settings_calls == ["community-1"]
    assert "Mode: disabled" in update.message.replies[0]["text"]
    assert "Join allowed: no" in update.message.replies[0]["text"]
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:set:preset:community-1:ready" in callbacks
    assert "eng:join:community-1" in callbacks
    assert "eng:detect:community-1:60" in callbacks


@pytest.mark.asyncio
async def test_set_engagement_ready_preset_preserves_safe_fields() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await set_engagement_command(update, _context(client, "community-1", "ready"))

    assert client.update_settings_calls == [
        {
            "community_id": "community-1",
            "updates": {
                "mode": "require_approval",
                "allow_join": True,
                "allow_post": True,
                "reply_only": True,
                "require_approval": True,
                "max_posts_per_day": 1,
                "min_minutes_between_posts": 240,
            },
        }
    ]
    assert "Mode: require_approval" in update.message.replies[0]["text"]
    assert "Join allowed: yes" in update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_settings_preset_callback_edits_settings_card() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:set:preset:community-1:observe")

    await callback_query(update, _context(client))

    assert client.update_settings_calls[0]["updates"]["mode"] == "observe"
    assert update.callback_query.answers == [{"text": None, "show_alert": False}]
    assert "Mode: observe" in update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_settings_join_toggle_callback_reads_then_patches_setting() -> None:
    client = _FakeApiClient()
    client.settings = {**client.settings, "mode": "suggest", "allow_post": False}
    update = _callback_update("eng:set:join:community-1:1")

    await callback_query(update, _context(client))

    assert client.get_settings_calls == ["community-1"]
    assert client.update_settings_calls[0]["updates"]["mode"] == "suggest"
    assert client.update_settings_calls[0]["updates"]["allow_join"] is True
    assert client.update_settings_calls[0]["updates"]["reply_only"] is True
    assert "Join allowed: yes" in update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_join_and_detect_commands_queue_explicit_jobs() -> None:
    client = _FakeApiClient()
    join_update = _message_update()
    detect_update = _message_update()

    await join_community_command(join_update, _context(client, "community-1"))
    await detect_engagement_command(detect_update, _context(client, "community-1", "45"))

    assert client.join_calls == [
        {"community_id": "community-1", "requested_by": "telegram:123:@operator"}
    ]
    assert client.detect_calls == [
        {
            "community_id": "community-1",
            "window_minutes": 45,
            "requested_by": "telegram:123:@operator",
        }
    ]
    assert "Community join queued." in join_update.message.replies[0]["text"]
    assert "Engagement detection queued." in detect_update.message.replies[0]["text"]
    assert "jb:join-job" in _callback_data_values(join_update.message.replies[0]["reply_markup"])
    assert "jb:detect-job" in _callback_data_values(detect_update.message.replies[0]["reply_markup"])


@pytest.mark.asyncio
async def test_join_and_detect_callbacks_queue_jobs() -> None:
    client = _FakeApiClient()
    join_update = _callback_update("eng:join:community-1")
    detect_update = _callback_update("eng:detect:community-1:60")

    await callback_query(join_update, _context(client))
    await callback_query(detect_update, _context(client))

    assert client.join_calls[0]["requested_by"] == "telegram:123:@operator"
    assert client.detect_calls[0]["window_minutes"] == 60
    assert "Community join queued." in join_update.callback_query.message.replies[0]["text"]
    assert "Engagement detection queued." in detect_update.callback_query.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_engagement_actions_command_filters_by_community_and_renders_audit() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_actions_command(update, _context(client, "community-1"))

    assert client.action_calls == [{"community_id": "community-1", "limit": 5, "offset": 0}]
    assert "Engagement audit (1-1 of 1)" in update.message.replies[0]["text"]
    assert "reply | failed" in update.message.replies[1]["text"]
    assert "Error: Flood wait" in update.message.replies[1]["text"]
    assert "Outbound text: Compare ownership" in update.message.replies[1]["text"]
    assert _callback_data_values(update.message.replies[0]["reply_markup"]) == [
        "eng:home",
        "op:home",
    ]


@pytest.mark.asyncio
async def test_engagement_actions_callback_pages_with_community_filter() -> None:
    client = _FakeApiClient()
    client.actions = [
        {**client.actions[0], "id": f"action-{index}", "community_id": "community-1"}
        for index in range(7)
    ]
    update = _callback_update("eng:actions:list:community-1:5")

    await callback_query(update, _context(client))

    assert client.action_calls == [{"community_id": "community-1", "limit": 5, "offset": 5}]
    assert "Engagement audit (6-7 of 7)" in update.callback_query.message.replies[0]["text"]
    callbacks = _callback_data_values(update.callback_query.message.replies[0]["reply_markup"])
    assert "eng:actions:list:community-1:0" in callbacks


@pytest.mark.asyncio
async def test_engagement_topics_command_lists_topic_cards_with_toggle_controls() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_topics_command(update, _context(client))

    assert "Engagement topics (1-2 of 2) | active 1" in update.message.replies[0]["text"]
    assert "Open CRM" in update.message.replies[1]["text"]
    assert "Triggers: crm, open source" in update.message.replies[1]["text"]
    assert "eng:topic:toggle:topic-1:0" in _callback_data_values(
        update.message.replies[1]["reply_markup"]
    )
    assert "eng:topic:toggle:topic-2:1" in _callback_data_values(
        update.message.replies[2]["reply_markup"]
    )


@pytest.mark.asyncio
async def test_create_engagement_topic_command_parses_pipe_syntax() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await create_engagement_topic_command(
        update,
        _context(
            client,
            "Open",
            "CRM",
            "|",
            "Be",
            "factual",
            "and",
            "brief.",
            "|",
            "crm,",
            "open",
            "source",
        ),
    )

    assert client.create_topic_calls == [
        {
            "name": "Open CRM",
            "stance_guidance": "Be factual and brief.",
            "trigger_keywords": ["crm", "open source"],
            "active": True,
        }
    ]
    assert "Engagement topic created." in update.message.replies[0]["text"]
    assert "Topic ID: topic-created" in update.message.replies[0]["text"]
    assert "eng:topic:toggle:topic-created:0" in _callback_data_values(
        update.message.replies[0]["reply_markup"]
    )


@pytest.mark.asyncio
async def test_create_engagement_topic_command_requires_keywords() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await create_engagement_topic_command(
        update,
        _context(client, "Open", "CRM", "|", "Be", "useful.", "|"),
    )

    assert "Usage: /create_engagement_topic" in update.message.replies[0]["text"]
    assert "at least one trigger keyword" in update.message.replies[0]["text"]
    assert client.create_topic_calls == []


@pytest.mark.asyncio
async def test_toggle_engagement_topic_command_updates_active_state() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await toggle_engagement_topic_command(update, _context(client, "topic-1", "off"))

    assert client.update_topic_calls == [{"topic_id": "topic-1", "updates": {"active": False}}]
    assert "Status: inactive" in update.message.replies[0]["text"]
    assert "eng:topic:toggle:topic-1:1" in _callback_data_values(
        update.message.replies[0]["reply_markup"]
    )


@pytest.mark.asyncio
async def test_toggle_engagement_topic_callback_edits_topic_card() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:topic:toggle:topic-1:0")

    await callback_query(update, _context(client))

    assert client.update_topic_calls == [{"topic_id": "topic-1", "updates": {"active": False}}]
    assert update.callback_query.answers == [{"text": None, "show_alert": False}]
    assert "Status: inactive" in update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_engagement_candidates_approved_status_exposes_send_not_review() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_candidates_command(update, _context(client, "approved"))

    assert "Engagement replies | approved" in update.message.replies[0]["text"]
    card = update.message.replies[1]
    callbacks = _callback_data_values(card["reply_markup"])
    assert "eng:cand:send:candidate-approved" in callbacks
    assert "eng:cand:approve:candidate-approved" not in callbacks
    assert client.list_candidate_calls[0]["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_reply_returns_queue_send_button_without_sending() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await approve_reply_command(update, _context(client, "candidate-review"))

    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "Queue send: /send_reply candidate-review" in update.message.replies[0]["text"]
    assert "eng:cand:send:candidate-review" in callbacks
    assert client.approve_calls == [
        {"candidate_id": "candidate-review", "reviewed_by": "telegram:123:@operator"}
    ]
    assert client.send_calls == []


@pytest.mark.asyncio
async def test_send_reply_command_queues_send_job() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await send_reply_command(update, _context(client, "candidate-approved"))

    assert "Reply send queued." in update.message.replies[0]["text"]
    assert "send-job (engagement.send)" in update.message.replies[0]["text"]
    assert client.send_calls == [
        {"candidate_id": "candidate-approved", "approved_by": "telegram:123:@operator"}
    ]
    assert "jb:send-job" in _callback_data_values(update.message.replies[0]["reply_markup"])


@pytest.mark.asyncio
async def test_send_reply_callback_queues_send_job() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:cand:send:candidate-approved")

    await callback_query(update, _context(client))

    assert update.callback_query.answers == [{"text": None, "show_alert": False}]
    assert "Reply send queued." in update.callback_query.message.replies[0]["text"]
    assert client.send_calls == [
        {"candidate_id": "candidate-approved", "approved_by": "telegram:123:@operator"}
    ]


@pytest.mark.asyncio
async def test_edit_reply_command_starts_guided_pending_edit() -> None:
    client = _FakeApiClient()
    context = _context(client, "candidate-review")
    update = _message_update()

    await edit_reply_command(update, context)

    assert "Editing Final reply" in update.message.replies[0]["text"]
    assert "Send the replacement value as your next message." in update.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.object_id == "candidate-review"
    assert client.edit_candidate_calls == []


@pytest.mark.asyncio
async def test_guided_edit_reply_previews_then_saves_latest_value() -> None:
    client = _FakeApiClient()
    context = _context(client, "candidate-review")
    start_update = _message_update()

    await edit_reply_command(start_update, context)
    text_update = _message_update("Compare data ownership and export access first.")
    await telegram_entity_text(text_update, context)

    preview = text_update.message.replies[0]
    assert "Review Final reply" in preview["text"]
    assert "Confirmation required before saving." in preview["text"]
    assert "Compare data ownership" in preview["text"]
    assert "eng:edit:save" in _callback_data_values(preview["reply_markup"])
    assert "eng:edit:cancel" in _callback_data_values(preview["reply_markup"])
    assert client.edit_candidate_calls == []

    save_update = _callback_update("eng:edit:save")
    await callback_query(save_update, context)

    assert client.edit_candidate_calls == [
        {
            "candidate_id": "candidate-review",
            "final_reply": "Compare data ownership and export access first.",
            "edited_by": "telegram:123:@operator",
            "edit_reason": None,
        }
    ]
    assert "Saved Final reply." in save_update.callback_query.edits[0]["text"]
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None


@pytest.mark.asyncio
async def test_guided_edit_save_is_scoped_to_operator() -> None:
    client = _FakeApiClient()
    context = _context(client, "candidate-review")

    await edit_reply_command(_message_update(), context)
    await telegram_entity_text(_message_update("Keep this scoped to the operator."), context)

    await callback_query(_callback_update("eng:edit:save", user_id=456), context)

    assert client.edit_candidate_calls == []
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is not None


@pytest.mark.asyncio
async def test_guided_edit_cancel_removes_only_callers_pending_edit() -> None:
    client = _FakeApiClient()
    context = _context(client, "candidate-review")

    await edit_reply_command(_message_update(), context)
    await telegram_entity_text(_message_update("Draft to cancel."), context)
    cancel_update = _callback_update("eng:edit:cancel")
    await callback_query(cancel_update, context)

    assert "Cancelled edit for Final reply." in cancel_update.callback_query.edits[0]["text"]
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None
    assert client.edit_candidate_calls == []
