from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.config_editing import PendingEditStore
from bot.config import BotSettings
from bot.main import (
    API_CLIENT_KEY,
    CONFIG_EDIT_STORE_KEY,
    add_engagement_target_command,
    approve_engagement_target_command,
    archive_engagement_target_command,
    activate_engagement_prompt_command,
    assign_engagement_account_command,
    callback_query,
    clear_engagement_account_command,
    clear_engagement_quiet_hours_command,
    create_engagement_prompt_command,
    create_style_rule_command,
    create_engagement_topic_command,
    detect_engagement_command,
    duplicate_engagement_prompt_command,
    edit_style_rule_command,
    edit_topic_guidance_command,
    edit_engagement_prompt_command,
    engagement_admin_command,
    engagement_actions_command,
    engagement_candidate_command,
    engagement_candidates_command,
    engagement_command,
    engagement_prompt_command,
    engagement_prompts_command,
    engagement_prompt_versions_command,
    engagement_rollout_command,
    engagement_settings_command,
    engagement_style_command,
    engagement_style_rule_command,
    engagement_topic_command,
    engagement_target_command,
    engagement_targets_command,
    engagement_topics_command,
    edit_reply_command,
    expire_candidate_command,
    join_community_command,
    reject_engagement_target_command,
    retry_candidate_command,
    resolve_engagement_target_command,
    rollback_engagement_prompt_command,
    send_reply_command,
    candidate_revisions_command,
    approve_reply_command,
    set_engagement_limits_command,
    set_engagement_quiet_hours_command,
    toggle_style_rule_command,
    target_detect_command,
    target_join_command,
    target_permission_command,
    topic_keywords_command,
    topic_remove_example_command,
    topic_good_reply_command,
    topic_bad_reply_command,
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
        self.get_candidate_calls: list[str] = []
        self.revision_calls: list[str] = []
        self.send_calls: list[dict[str, Any]] = []
        self.approve_calls: list[dict[str, Any]] = []
        self.edit_candidate_calls: list[dict[str, Any]] = []
        self.expire_candidate_calls: list[dict[str, Any]] = []
        self.retry_candidate_calls: list[dict[str, Any]] = []
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
        self.get_prompt_calls: list[str] = []
        self.preview_prompt_calls: list[str] = []
        self.prompt_versions_calls: list[str] = []
        self.create_prompt_calls: list[dict[str, Any]] = []
        self.activate_prompt_calls: list[dict[str, Any]] = []
        self.duplicate_prompt_calls: list[dict[str, Any]] = []
        self.rollback_prompt_calls: list[dict[str, Any]] = []
        self.update_prompt_calls: list[dict[str, Any]] = []
        self.style_list_calls: list[dict[str, Any]] = []
        self.get_style_rule_calls: list[str] = []
        self.create_style_rule_calls: list[dict[str, Any]] = []
        self.update_style_rule_calls: list[dict[str, Any]] = []
        self.get_topic_calls: list[str] = []
        self.add_topic_example_calls: list[dict[str, Any]] = []
        self.remove_topic_example_calls: list[dict[str, Any]] = []
        self.join_calls: list[dict[str, Any]] = []
        self.detect_calls: list[dict[str, Any]] = []
        self.action_calls: list[dict[str, Any]] = []
        self.rollout_calls: list[dict[str, Any]] = []
        self.accounts_calls = 0
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
        self.accounts = {
            "counts": {"available": 1, "in_use": 0, "rate_limited": 0, "banned": 0},
            "items": [
                {
                    "id": "12345678-1234-1234-1234-123456789abc",
                    "phone": "+123*****89",
                    "status": "available",
                }
            ],
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
                "example_good_replies": ["Compare export paths first."],
                "example_bad_replies": ["Buy our tool now."],
                "active": True,
            },
            {
                "id": "topic-2",
                "name": "Automation",
                "stance_guidance": "Discuss practical automation tradeoffs.",
                "trigger_keywords": ["automation"],
                "negative_keywords": [],
                "example_good_replies": [],
                "example_bad_replies": [],
                "active": False,
            },
        ]
        self.style_rules = [
            {
                "id": "rule-1",
                "scope_type": "global",
                "scope_id": None,
                "name": "Keep it brief",
                "rule_text": "Keep replies under three sentences.",
                "active": True,
                "priority": 50,
                "created_by": "operator",
                "updated_by": "operator",
                "created_at": "2026-04-19T10:00:00Z",
                "updated_at": "2026-04-19T10:00:00Z",
            },
            {
                "id": "rule-2",
                "scope_type": "community",
                "scope_id": "community-1",
                "name": "Mention tradeoffs",
                "rule_text": "Mention tradeoffs before recommendations.",
                "active": False,
                "priority": 100,
                "created_by": "operator",
                "updated_by": "operator",
                "created_at": "2026-04-19T10:00:00Z",
                "updated_at": "2026-04-19T10:00:00Z",
            },
            {
                "id": "rule-3",
                "scope_type": "account",
                "scope_id": "account-1",
                "name": "Be transparent",
                "rule_text": "Be transparent about uncertainty.",
                "active": True,
                "priority": 120,
                "created_by": "operator",
                "updated_by": "operator",
                "created_at": "2026-04-19T10:00:00Z",
                "updated_at": "2026-04-19T10:00:00Z",
            },
            {
                "id": "rule-4",
                "scope_type": "topic",
                "scope_id": "topic-1",
                "name": "Lead with tradeoffs",
                "rule_text": "Lead with tradeoffs before preferences.",
                "active": True,
                "priority": 150,
                "created_by": "operator",
                "updated_by": "operator",
                "created_at": "2026-04-19T10:00:00Z",
                "updated_at": "2026-04-19T10:00:00Z",
            },
        ]
        self.prompts = [
            {
                "id": "prompt-active",
                "name": "Default",
                "description": "Primary engagement prompt.",
                "active": True,
                "model": "gpt-4.1-mini",
                "temperature": 0.2,
                "max_output_tokens": 1000,
                "system_prompt": "Stay public-only and helpful.",
                "user_prompt_template": "Community: {{community.title}}\nSource: {{source_post.text}}",
                "output_schema_name": "engagement_detection_v1",
                "current_version_number": 2,
                "current_version_id": "prompt-version-2",
                "created_by": "operator",
                "updated_by": "operator",
                "created_at": "2026-04-19T10:00:00Z",
                "updated_at": "2026-04-19T11:00:00Z",
            },
            {
                "id": "prompt-draft",
                "name": "Draft",
                "description": None,
                "active": False,
                "model": "gpt-4.1-mini",
                "temperature": 0.1,
                "max_output_tokens": 800,
                "system_prompt": "Draft concise replies.",
                "user_prompt_template": "Topic: {{topic.name}}",
                "output_schema_name": "engagement_detection_v1",
                "current_version_number": 1,
                "current_version_id": "prompt-version-1",
                "created_by": "operator",
                "updated_by": "operator",
                "created_at": "2026-04-19T10:00:00Z",
                "updated_at": "2026-04-19T10:00:00Z",
            },
        ]
        self.prompt_versions = {
            "prompt-active": [
                {
                    "id": "prompt-version-2",
                    "prompt_profile_id": "prompt-active",
                    "version_number": 2,
                    "model": "gpt-4.1-mini",
                    "temperature": 0.2,
                    "max_output_tokens": 1000,
                    "system_prompt": "Stay public-only and helpful.",
                    "user_prompt_template": "Community: {{community.title}}\nSource: {{source_post.text}}",
                    "output_schema_name": "engagement_detection_v1",
                    "created_by": "operator",
                    "created_at": "2026-04-19T11:00:00Z",
                },
                {
                    "id": "prompt-version-1",
                    "prompt_profile_id": "prompt-active",
                    "version_number": 1,
                    "model": "gpt-4.1-mini",
                    "temperature": 0.1,
                    "max_output_tokens": 800,
                    "system_prompt": "Older public-only guidance.",
                    "user_prompt_template": "Topic: {{topic.name}}",
                    "output_schema_name": "engagement_detection_v1",
                    "created_by": "operator",
                    "created_at": "2026-04-19T10:00:00Z",
                },
            ]
        }
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
        self.rollout = {
            "window_days": 14,
            "total_semantic_candidates": 2,
            "reviewed_semantic_candidates": 2,
            "approved": 1,
            "rejected": 1,
            "pending": 0,
            "expired": 0,
            "approval_rate": 0.5,
            "bands": [
                {
                    "label": "0.80-0.89",
                    "total": 1,
                    "approved": 1,
                    "rejected": 0,
                    "pending": 0,
                    "expired": 0,
                    "approval_rate": 1.0,
                }
            ],
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
        return {
            "items": self.prompts[offset : offset + limit],
            "total": len(self.prompts),
            "limit": limit,
            "offset": offset,
        }

    async def get_engagement_prompt_profile(self, profile_id: str) -> dict[str, Any]:
        self.get_prompt_calls.append(profile_id)
        prompt = next((item for item in self.prompts if item["id"] == profile_id), None)
        return dict(prompt or {**self.prompts[0], "id": profile_id})

    async def preview_engagement_prompt_profile(
        self,
        profile_id: str,
        *,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.preview_prompt_calls.append(profile_id)
        prompt = await self.get_engagement_prompt_profile(profile_id)
        return {
            "profile_id": profile_id,
            "profile_name": prompt["name"],
            "version_id": prompt["current_version_id"],
            "version_number": prompt["current_version_number"],
            "model": prompt["model"],
            "temperature": prompt["temperature"],
            "max_output_tokens": prompt["max_output_tokens"],
            "system_prompt": prompt["system_prompt"],
            "rendered_user_prompt": "Community: Founder Circle\nSource: Discussing CRM tools.",
            "variables": variables or {},
        }

    async def list_engagement_prompt_profile_versions(self, profile_id: str) -> dict[str, Any]:
        self.prompt_versions_calls.append(profile_id)
        return {"items": list(self.prompt_versions.get(profile_id, []))}

    async def create_engagement_prompt_profile(self, **payload: Any) -> dict[str, Any]:
        self.create_prompt_calls.append(dict(payload))
        profile = {
            "id": "prompt-created",
            "name": payload["name"],
            "description": payload.get("description"),
            "active": payload.get("active", False),
            "model": payload["model"],
            "temperature": payload["temperature"],
            "max_output_tokens": payload["max_output_tokens"],
            "system_prompt": payload["system_prompt"],
            "user_prompt_template": payload["user_prompt_template"],
            "output_schema_name": payload.get("output_schema_name", "engagement_detection_v1"),
            "current_version_number": 1,
            "current_version_id": "prompt-created-version-1",
            "created_by": payload.get("created_by") or "operator",
            "updated_by": payload.get("created_by") or "operator",
            "created_at": "2026-04-22T10:00:00Z",
            "updated_at": "2026-04-22T10:00:00Z",
        }
        self.prompts.append(profile)
        return profile

    async def activate_engagement_prompt_profile(
        self,
        profile_id: str,
        *,
        updated_by: str | None = None,
    ) -> dict[str, Any]:
        self.activate_prompt_calls.append({"profile_id": profile_id, "updated_by": updated_by})
        self.prompts = [
            {**item, "active": item["id"] == profile_id}
            for item in self.prompts
        ]
        return await self.get_engagement_prompt_profile(profile_id)

    async def duplicate_engagement_prompt_profile(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        self.duplicate_prompt_calls.append(
            {"profile_id": profile_id, "name": name, "created_by": created_by}
        )
        source = await self.get_engagement_prompt_profile(profile_id)
        duplicate = {
            **source,
            "id": "prompt-copy",
            "name": name or f"{source['name']} copy",
            "active": False,
            "current_version_number": 1,
            "current_version_id": "prompt-copy-version-1",
            "created_by": created_by or "operator",
            "updated_by": created_by or "operator",
        }
        self.prompts.append(duplicate)
        return duplicate

    async def rollback_engagement_prompt_profile(
        self,
        profile_id: str,
        *,
        version_id: str,
        updated_by: str | None = None,
    ) -> dict[str, Any]:
        self.rollback_prompt_calls.append(
            {"profile_id": profile_id, "version_id": version_id, "updated_by": updated_by}
        )
        prompt = await self.get_engagement_prompt_profile(profile_id)
        return {**prompt, "current_version_number": 3, "current_version_id": "prompt-version-3"}

    async def update_engagement_prompt_profile(self, profile_id: str, **updates: Any) -> dict[str, Any]:
        self.update_prompt_calls.append({"profile_id": profile_id, "updates": updates})
        prompt = await self.get_engagement_prompt_profile(profile_id)
        changed = {**prompt, **{key: value for key, value in updates.items() if key != "updated_by"}}
        changed["current_version_number"] = int(changed.get("current_version_number") or 0) + 1
        self.prompts = [changed if item["id"] == profile_id else item for item in self.prompts]
        return changed

    async def list_engagement_style_rules(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        limit: int = 5,
        offset: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        self.style_list_calls.append(
            {"scope_type": scope_type, "scope_id": scope_id, "limit": limit, "offset": offset}
        )
        items = [
            rule
            for rule in self.style_rules
            if (scope_type is None or rule["scope_type"] == scope_type)
            and (scope_id is None or rule["scope_id"] == scope_id)
        ]
        return {"items": items[offset : offset + limit], "total": len(items), "limit": limit, "offset": offset}

    async def get_engagement_style_rule(self, rule_id: str) -> dict[str, Any]:
        self.get_style_rule_calls.append(rule_id)
        rule = next((item for item in self.style_rules if item["id"] == rule_id), None)
        return dict(rule or {**self.style_rules[0], "id": rule_id})

    async def create_engagement_style_rule(self, **payload: Any) -> dict[str, Any]:
        self.create_style_rule_calls.append(dict(payload))
        rule = {
            "id": "rule-created",
            "active": True,
            "created_by": payload.get("created_by") or "operator",
            "updated_by": payload.get("created_by") or "operator",
            "created_at": "2026-04-21T10:00:00Z",
            "updated_at": "2026-04-21T10:00:00Z",
            **payload,
        }
        self.style_rules.append(rule)
        return rule

    async def update_engagement_style_rule(self, rule_id: str, **updates: Any) -> dict[str, Any]:
        self.update_style_rule_calls.append({"rule_id": rule_id, "updates": updates})
        rule = await self.get_engagement_style_rule(rule_id)
        updated = {**rule, **{key: value for key, value in updates.items() if key != "updated_by"}}
        updated["updated_by"] = updates.get("updated_by") or rule.get("updated_by")
        self.style_rules = [updated if item["id"] == rule_id else item for item in self.style_rules]
        return updated

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

    async def get_engagement_candidate(self, candidate_id: str) -> dict[str, Any]:
        self.get_candidate_calls.append(candidate_id)
        for page in self.candidates_by_status.values():
            for candidate in page["items"]:
                if candidate["id"] == candidate_id:
                    return dict(candidate)
        return {
            "id": candidate_id,
            "community_title": "Founder Circle",
            "topic_name": "Open CRM",
            "status": "needs_review",
            "source_excerpt": "Discussing CRM tools.",
            "detected_reason": "Relevant CRM discussion.",
            "suggested_reply": "Compare ownership and integrations first.",
            "prompt_render_summary": {"profile_name": "Default", "version_number": 3},
            "prompt_profile_version_id": "version-3",
            "risk_notes": ["Keep it factual."],
        }

    async def list_engagement_candidate_revisions(self, candidate_id: str) -> dict[str, Any]:
        self.revision_calls.append(candidate_id)
        return {
            "items": [
                {
                    "id": "revision-1",
                    "candidate_id": candidate_id,
                    "revision_number": 1,
                    "reply_text": "Edited reply text.",
                    "edited_by": "telegram:123",
                    "edit_reason": "manual edit",
                    "created_at": "2026-04-21T10:00:00Z",
                }
            ],
            "total": 1,
        }

    async def list_engagement_topics(self) -> dict[str, Any]:
        return {"items": self.topics, "total": len(self.topics)}

    async def get_engagement_topic(self, topic_id: str) -> dict[str, Any]:
        self.get_topic_calls.append(topic_id)
        topic = next((item for item in self.topics if item["id"] == topic_id), None)
        return dict(topic or {**self.topics[0], "id": topic_id})

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
            "example_good_replies": [],
            "example_bad_replies": [],
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
                "example_good_replies": [],
                "example_bad_replies": [],
                "active": True,
            }
        updated = {**topic, **updates}
        self.topics = [updated if item["id"] == topic_id else item for item in self.topics]
        return updated

    async def add_engagement_topic_example(
        self,
        topic_id: str,
        *,
        example_type: str,
        example: str,
    ) -> dict[str, Any]:
        self.add_topic_example_calls.append(
            {"topic_id": topic_id, "example_type": example_type, "example": example}
        )
        topic = await self.get_engagement_topic(topic_id)
        if example_type == "good":
            topic["example_good_replies"] = [*(topic.get("example_good_replies") or []), example]
        else:
            topic["example_bad_replies"] = [*(topic.get("example_bad_replies") or []), example]
        self.topics = [topic if item["id"] == topic_id else item for item in self.topics]
        return topic

    async def remove_engagement_topic_example(
        self,
        topic_id: str,
        *,
        example_type: str,
        index: int,
    ) -> dict[str, Any]:
        self.remove_topic_example_calls.append(
            {"topic_id": topic_id, "example_type": example_type, "index": index}
        )
        topic = await self.get_engagement_topic(topic_id)
        key = "example_good_replies" if example_type == "good" else "example_bad_replies"
        values = list(topic.get(key) or [])
        if values and 0 <= index < len(values):
            values.pop(index)
        topic[key] = values
        self.topics = [topic if item["id"] == topic_id else item for item in self.topics]
        return topic

    async def get_engagement_settings(self, community_id: str) -> dict[str, Any]:
        self.get_settings_calls.append(community_id)
        return {**self.settings, "community_id": community_id}

    async def update_engagement_settings(self, community_id: str, **updates: Any) -> dict[str, Any]:
        self.update_settings_calls.append({"community_id": community_id, "updates": updates})
        self.settings = {**self.settings, **updates, "community_id": community_id}
        return self.settings

    async def get_accounts(self) -> dict[str, Any]:
        self.accounts_calls += 1
        return self.accounts

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

    async def get_engagement_semantic_rollout(
        self,
        *,
        window_days: int = 14,
        **_: Any,
    ) -> dict[str, Any]:
        self.rollout_calls.append({"window_days": window_days})
        return {**self.rollout, "window_days": window_days}

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

    async def expire_engagement_candidate(
        self,
        candidate_id: str,
        *,
        expired_by: str | None = None,
    ) -> dict[str, Any]:
        self.expire_candidate_calls.append({"candidate_id": candidate_id, "expired_by": expired_by})
        return {
            "id": candidate_id,
            "community_title": "Founder Circle",
            "topic_name": "Open CRM",
            "status": "expired",
            "source_excerpt": "Discussing CRM tools.",
            "detected_reason": "Relevant CRM discussion.",
            "suggested_reply": "Compare ownership and integrations first.",
        }

    async def retry_engagement_candidate(
        self,
        candidate_id: str,
        *,
        retried_by: str | None = None,
    ) -> dict[str, Any]:
        self.retry_candidate_calls.append({"candidate_id": candidate_id, "retried_by": retried_by})
        return {
            "id": candidate_id,
            "community_title": "Founder Circle",
            "topic_name": "Open CRM",
            "status": "needs_review",
            "source_excerpt": "Discussing CRM tools.",
            "detected_reason": "Relevant CRM discussion.",
            "suggested_reply": "Compare ownership and integrations first.",
        }


def _settings(*, admin_user_ids: tuple[int, ...] = ()) -> BotSettings:
    return BotSettings(
        telegram_bot_token="telegram-token",
        api_base_url="http://api.test/api",
        api_token="api-token",
        allowed_user_ids=frozenset({123, 456}),
        admin_user_ids=frozenset(admin_user_ids),
    )


def _context(
    client: _FakeApiClient,
    *args: str,
    settings: BotSettings | None = None,
) -> SimpleNamespace:
    bot_data = {API_CLIENT_KEY: client}
    if settings is not None:
        bot_data["settings"] = settings
    return SimpleNamespace(
        args=list(args),
        application=SimpleNamespace(bot_data=bot_data),
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
async def test_prompt_profile_command_opens_detail_with_admin_controls() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_prompt_command(update, _context(client, "prompt-active"))

    assert client.get_prompt_calls == ["prompt-active"]
    text = update.message.replies[0]["text"]
    assert "Profile ID: prompt-active" in text
    assert "System: Stay public-only" in text
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:admin:pp:prompt-active" in callbacks
    assert "eng:admin:pv:prompt-active" in callbacks
    assert "eng:admin:pe:prompt-active:s" in callbacks
    assert "eng:admin:pe:prompt-active:u" in callbacks


@pytest.mark.asyncio
async def test_prompt_profile_versions_and_rollback_confirm_then_save() -> None:
    client = _FakeApiClient()
    versions_update = _message_update()
    confirm_update = _message_update()
    save_update = _callback_update("eng:admin:prbc:prompt-active:1")

    await engagement_prompt_versions_command(versions_update, _context(client, "prompt-active"))
    await rollback_engagement_prompt_command(confirm_update, _context(client, "prompt-active", "1"))
    await callback_query(save_update, _context(client))

    assert client.prompt_versions_calls == ["prompt-active", "prompt-active", "prompt-active"]
    assert "Version 1" in versions_update.message.replies[0]["text"]
    assert "Confirm prompt rollback" in confirm_update.message.replies[0]["text"]
    assert client.rollback_prompt_calls == [
        {
            "profile_id": "prompt-active",
            "version_id": "prompt-version-1",
            "updated_by": "telegram:123:@operator",
        }
    ]
    assert "Prompt profile rolled back." in save_update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_prompt_profile_activate_requires_confirmation() -> None:
    client = _FakeApiClient()
    confirm_update = _message_update()
    save_update = _callback_update("eng:admin:pac:prompt-draft")

    await activate_engagement_prompt_command(confirm_update, _context(client, "prompt-draft"))
    await callback_query(save_update, _context(client))

    assert client.activate_prompt_calls == [
        {"profile_id": "prompt-draft", "updated_by": "telegram:123:@operator"}
    ]
    assert "Confirm prompt activation" in confirm_update.message.replies[0]["text"]
    assert "Status: active" in save_update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_non_admin_cannot_open_prompt_admin_surfaces() -> None:
    client = _FakeApiClient()
    settings = _settings(admin_user_ids=(999,))
    command_update = _message_update()
    callback_update = _callback_update("eng:admin:pa:prompt-active")

    await engagement_prompts_command(command_update, _context(client, settings=settings))
    await callback_query(callback_update, _context(client, settings=settings))

    assert client.prompt_list_calls == []
    assert client.get_prompt_calls == []
    assert command_update.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )
    assert callback_update.callback_query.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )


@pytest.mark.asyncio
async def test_prompt_profile_edit_guided_flow_rejects_private_variables_before_api_call() -> None:
    client = _FakeApiClient()
    context = _context(client, "prompt-active", "user_prompt_template")

    await edit_engagement_prompt_command(_message_update(), context)
    text_update = _message_update("Sender: {{sender.username}}")
    await telegram_entity_text(text_update, context)

    assert "Unsupported prompt variable: sender.username" in text_update.message.replies[0]["text"]
    assert client.update_prompt_calls == []


@pytest.mark.asyncio
async def test_prompt_profile_edit_guided_flow_saves_allowlisted_field() -> None:
    client = _FakeApiClient()
    context = _context(client, "prompt-active", "system_prompt")

    await edit_engagement_prompt_command(_message_update(), context)
    await telegram_entity_text(_message_update("Stay public-only and concise."), context)
    await callback_query(_callback_update("eng:edit:save"), context)

    assert client.update_prompt_calls == [
        {
            "profile_id": "prompt-active",
            "updates": {
                "system_prompt": "Stay public-only and concise.",
                "updated_by": "telegram:123:@operator",
            },
        }
    ]


@pytest.mark.asyncio
async def test_duplicate_prompt_profile_command_uses_prompt_api() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await duplicate_engagement_prompt_command(update, _context(client, "prompt-active", "New", "voice"))

    assert client.duplicate_prompt_calls == [
        {
            "profile_id": "prompt-active",
            "name": "New voice",
            "created_by": "telegram:123:@operator",
        }
    ]
    assert "Prompt profile duplicated." in update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_create_prompt_profile_command_uses_prompt_api_and_rejects_private_variables() -> None:
    client = _FakeApiClient()
    create_update = _message_update()
    bad_update = _message_update()

    await create_engagement_prompt_command(
        create_update,
        _context(
            client,
            "New",
            "profile",
            "|",
            "-",
            "|",
            "gpt-4.1-mini",
            "|",
            "0.3",
            "|",
            "900",
            "|",
            "Stay public-only.",
            "|",
            "Community: {{community.title}} Source: {{source_post.text}}",
        ),
    )
    await create_engagement_prompt_command(
        bad_update,
        _context(
            client,
            "Bad",
            "|",
            "-",
            "|",
            "gpt-4.1-mini",
            "|",
            "0.3",
            "|",
            "900",
            "|",
            "System",
            "|",
            "Sender: {{sender.username}}",
        ),
    )

    assert client.create_prompt_calls == [
        {
            "name": "New profile",
            "description": None,
            "active": False,
            "model": "gpt-4.1-mini",
            "temperature": 0.3,
            "max_output_tokens": 900,
            "system_prompt": "Stay public-only.",
            "user_prompt_template": "Community: {{community.title}} Source: {{source_post.text}}",
            "output_schema_name": "engagement_detection_v1",
            "created_by": "telegram:123:@operator",
        }
    ]
    assert "Prompt profile created." in create_update.message.replies[0]["text"]
    assert "Unsupported prompt variable: sender.username" in bad_update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_prompt_profile_inline_create_flow_previews_then_saves() -> None:
    client = _FakeApiClient()
    context = _context(client)
    start_update = _callback_update("eng:admin:pc")
    text_update = _message_update(
        "Inline profile | Guided path | gpt-4.1-mini | 0.2 | 1000 | "
        "Stay public-only. | Community: {{community.title}}"
    )
    save_update = _callback_update("eng:edit:save")

    await callback_query(start_update, context)
    await telegram_entity_text(text_update, context)
    await callback_query(save_update, context)

    assert "Editing Prompt profile creation details" in start_update.callback_query.message.replies[0]["text"]
    assert "Review Prompt profile creation details" in text_update.message.replies[0]["text"]
    assert client.create_prompt_calls[-1]["name"] == "Inline profile"
    assert client.create_prompt_calls[-1]["created_by"] == "telegram:123:@operator"
    assert "Prompt profile created." in save_update.callback_query.edits[0]["text"]


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
async def test_approve_target_command_requires_confirmation_before_mutation() -> None:
    client = _FakeApiClient()
    context = _context(client, "target-resolved")
    update = _message_update()

    await approve_engagement_target_command(update, context)

    assert client.update_target_calls == []
    assert "Confirm target approval" in update.message.replies[0]["text"]
    assert "After: status=approved, join=yes, detect=yes, post=yes" in update.message.replies[0]["text"]
    assert "eng:admin:tac:target-resolved" in _callback_data_values(
        update.message.replies[0]["reply_markup"]
    )

    await callback_query(_callback_update("eng:admin:tac:target-resolved"), context)

    assert client.update_target_calls == [
        {
            "target_id": "target-resolved",
            "updates": {
                "status": "approved",
                "allow_join": True,
                "allow_detect": True,
                "allow_post": True,
                "updated_by": "telegram:123:@operator",
            },
        }
    ]


@pytest.mark.asyncio
async def test_target_permission_post_command_requires_confirmation_before_mutation() -> None:
    client = _FakeApiClient()
    context = _context(client, "target-approved", "post", "on")
    update = _message_update()

    await target_permission_command(update, context)

    assert client.update_target_calls == []
    message = update.message.replies[0]["text"]
    assert "Confirm target post permission change" in message
    assert "Before: status=approved, join=yes, detect=yes, post=no" in message
    assert "After: status=approved, join=yes, detect=yes, post=yes" in message
    assert "eng:admin:tpc:target-approved:p:1" in _callback_data_values(
        update.message.replies[0]["reply_markup"]
    )

    await callback_query(_callback_update("eng:admin:tpc:target-approved:p:1"), context)

    assert client.update_target_calls == [
        {
            "target_id": "target-approved",
            "updates": {"allow_post": True, "updated_by": "telegram:123:@operator"},
        }
    ]


@pytest.mark.asyncio
async def test_target_permission_join_command_still_saves_directly() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await target_permission_command(update, _context(client, "target-approved", "join", "off"))

    assert client.update_target_calls[-1] == {
        "target_id": "target-approved",
        "updates": {"allow_join": False, "updated_by": "telegram:123:@operator"},
    }
    message = update.message.replies[0]["text"]
    assert "Before: status=approved, join=yes, detect=yes, post=no" in message
    assert "After: status=approved, join=no, detect=yes, post=no" in message


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
    confirm_update = _callback_update("eng:admin:tpc:target-approved:p:1")
    join_update = _callback_update("eng:admin:tj:target-approved")
    detect_update = _callback_update("eng:admin:td:target-approved:60")

    await callback_query(open_update, _context(client))
    await callback_query(toggle_update, _context(client))
    await callback_query(confirm_update, _context(client))
    await callback_query(join_update, _context(client))
    await callback_query(detect_update, _context(client))

    assert "Target ID: target-approved" in open_update.callback_query.message.replies[0]["text"]
    assert "Confirm target post permission change" in toggle_update.callback_query.edits[0]["text"]
    assert "After: status=approved" in confirm_update.callback_query.edits[0]["text"]
    assert client.target_join_calls[-1]["target_id"] == "target-approved"
    assert client.target_detect_calls[-1]["window_minutes"] == 60


@pytest.mark.asyncio
async def test_target_notes_button_guided_edit_previews_then_saves() -> None:
    client = _FakeApiClient()
    context = _context(client)
    start_update = _callback_update("eng:admin:te:target-approved:notes")

    await callback_query(start_update, context)

    assert "Editing Target notes" in start_update.callback_query.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "target"
    assert pending.object_id == "target-approved"
    assert pending.field == "notes"

    text_update = _message_update("Warm founder community; keep replies concise.")
    await telegram_entity_text(text_update, context)

    assert "Review Target notes" in text_update.message.replies[0]["text"]
    assert client.update_target_calls == []

    save_update = _callback_update("eng:edit:save")
    await callback_query(save_update, context)

    assert client.update_target_calls == [
        {
            "target_id": "target-approved",
            "updates": {
                "notes": "Warm founder community; keep replies concise.",
                "updated_by": "telegram:123:@operator",
            },
        }
    ]
    assert "Saved Target notes." in save_update.callback_query.edits[0]["text"]
    assert "Notes: Warm founder community" in save_update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_target_notes_guided_edit_cancel_and_expiry_do_not_save() -> None:
    client = _FakeApiClient()
    cancel_context = _context(client)

    await callback_query(_callback_update("eng:admin:te:target-approved:notes"), cancel_context)
    await telegram_entity_text(_message_update("Draft note to discard."), cancel_context)
    cancel_update = _callback_update("eng:edit:cancel")
    await callback_query(cancel_update, cancel_context)

    assert "Cancelled edit for Target notes." in cancel_update.callback_query.edits[0]["text"]

    expired_context = _context(client)
    expired_context.application.bot_data[CONFIG_EDIT_STORE_KEY] = PendingEditStore(
        timeout_seconds=-1
    )
    await callback_query(_callback_update("eng:admin:te:target-approved:notes"), expired_context)
    save_update = _callback_update("eng:edit:save")
    await callback_query(save_update, expired_context)

    assert "No pending edit to save." in save_update.callback_query.message.replies[0]["text"]
    assert client.update_target_calls == []


@pytest.mark.asyncio
async def test_non_admin_cannot_approve_target_or_toggle_target_permissions() -> None:
    client = _FakeApiClient()
    settings = _settings(admin_user_ids=(999,))
    approve_update = _message_update()
    toggle_update = _callback_update("eng:admin:tp:target-approved:p:1")
    edit_update = _callback_update("eng:admin:te:target-approved:notes")
    approve_confirm_update = _callback_update("eng:admin:tac:target-approved")
    post_confirm_update = _callback_update("eng:admin:tpc:target-approved:p:1")

    await approve_engagement_target_command(
        approve_update,
        _context(client, "target-approved", settings=settings),
    )
    await callback_query(toggle_update, _context(client, settings=settings))
    await callback_query(edit_update, _context(client, settings=settings))
    await callback_query(approve_confirm_update, _context(client, settings=settings))
    await callback_query(post_confirm_update, _context(client, settings=settings))

    assert client.update_target_calls == []
    assert approve_update.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )
    assert toggle_update.callback_query.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )
    assert edit_update.callback_query.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )
    assert approve_confirm_update.callback_query.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )
    assert post_confirm_update.callback_query.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )


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
@pytest.mark.parametrize(
    ("callback_data", "new_value", "expected_field", "expected_value", "preview_label"),
    [
        (
            "eng:set:e:community-1:mp",
            "3",
            "max_posts_per_day",
            3,
            "Max posts per day",
        ),
        (
            "eng:set:e:community-1:qs",
            "22:30",
            "quiet_hours_start",
            "22:30",
            "Quiet hours start",
        ),
        (
            "eng:set:e:community-1:acct",
            "12345678-1234-1234-1234-123456789abc",
            "assigned_account_id",
            "12345678-1234-1234-1234-123456789abc",
            "Assigned engagement account",
        ),
    ],
)
async def test_settings_guided_edit_buttons_preserve_safe_fields(
    callback_data: str,
    new_value: str,
    expected_field: str,
    expected_value: object,
    preview_label: str,
) -> None:
    client = _FakeApiClient()
    client.settings = {
        **client.settings,
        "mode": "suggest",
        "allow_join": True,
        "allow_post": True,
        "quiet_hours_start": "20:00",
        "quiet_hours_end": "07:00",
    }
    context = _context(client)
    start_update = _callback_update(callback_data)

    await callback_query(start_update, context)

    assert f"Editing {preview_label}" in start_update.callback_query.message.replies[0]["text"]

    await telegram_entity_text(_message_update(new_value), context)
    assert client.update_settings_calls == []

    save_update = _callback_update("eng:edit:save")
    await callback_query(save_update, context)

    updates = client.update_settings_calls[0]["updates"]
    assert updates[expected_field] == expected_value
    assert updates["reply_only"] is True
    assert updates["require_approval"] is True
    assert updates["mode"] == "suggest"
    assert updates["allow_join"] is True
    assert updates["allow_post"] is True
    assert "Saved" in save_update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_set_engagement_limits_command_preserves_safe_fields() -> None:
    client = _FakeApiClient()
    client.settings = {
        **client.settings,
        "mode": "require_approval",
        "allow_join": True,
        "allow_post": True,
    }
    update = _message_update()

    await set_engagement_limits_command(update, _context(client, "community-1", "2", "180"))

    assert client.get_settings_calls == ["community-1"]
    assert client.update_settings_calls == [
        {
            "community_id": "community-1",
            "updates": {
                "mode": "require_approval",
                "allow_join": True,
                "allow_post": True,
                "reply_only": True,
                "require_approval": True,
                "max_posts_per_day": 2,
                "min_minutes_between_posts": 180,
                "quiet_hours_start": None,
                "quiet_hours_end": None,
                "assigned_account_id": None,
            },
        }
    ]
    assert "Rate limit: 2 per day, 180 minutes apart" in update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_set_engagement_quiet_hours_command_validates_time_before_api_call() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await set_engagement_quiet_hours_command(update, _context(client, "community-1", "25:00", "07:00"))

    assert client.get_settings_calls == []
    assert client.update_settings_calls == []
    assert update.message.replies[0]["text"] == "Quiet hours start must use HH:MM time."


@pytest.mark.asyncio
async def test_clear_engagement_quiet_hours_command_clears_both_values() -> None:
    client = _FakeApiClient()
    client.settings = {
        **client.settings,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "07:00",
    }
    update = _message_update()

    await clear_engagement_quiet_hours_command(update, _context(client, "community-1"))

    assert client.update_settings_calls == [
        {
            "community_id": "community-1",
            "updates": {
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
            },
        }
    ]
    assert "Quiet hours: 22:00-07:00" not in update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_assign_engagement_account_command_uses_uuid_and_masked_label() -> None:
    client = _FakeApiClient()
    context = _context(client, "community-1", "12345678-1234-1234-1234-123456789abc")
    update = _message_update()
    account_id = "12345678-1234-1234-1234-123456789abc"

    await assign_engagement_account_command(update, context)

    assert client.update_settings_calls == []
    preview_text = update.message.replies[0]["text"]
    assert "Confirm engagement account assignment" in preview_text
    assert "Before: none" in preview_text
    assert f"After: {account_id} | +123*****89" in preview_text
    assert "+123456789" not in preview_text
    assert "eng:set:acctc" in _callback_data_values(update.message.replies[0]["reply_markup"])

    confirm_update = _callback_update("eng:set:acctc")
    await callback_query(confirm_update, context)

    assert client.update_settings_calls == [
        {
            "community_id": "community-1",
            "updates": {
                "mode": "disabled",
                "allow_join": False,
                "allow_post": False,
                "reply_only": True,
                "require_approval": True,
                "max_posts_per_day": 1,
                "min_minutes_between_posts": 240,
                "quiet_hours_start": None,
                "quiet_hours_end": None,
                "assigned_account_id": account_id,
            },
        }
    ]
    assert client.accounts_calls == 2
    text = confirm_update.callback_query.edits[0]["text"]
    assert f"Assigned account: {account_id} | +123*****89" in text
    assert "+123456789" not in text


@pytest.mark.asyncio
async def test_clear_engagement_account_command_removes_assignment() -> None:
    client = _FakeApiClient()
    client.settings = {
        **client.settings,
        "assigned_account_id": "12345678-1234-1234-1234-123456789abc",
    }
    context = _context(client, "community-1")
    update = _message_update()

    await clear_engagement_account_command(update, context)

    assert client.update_settings_calls == []
    preview_text = update.message.replies[0]["text"]
    assert "Confirm engagement account assignment" in preview_text
    assert "Before: 12345678-1234-1234-1234-123456789abc | +123*****89" in preview_text
    assert "After: none" in preview_text

    confirm_update = _callback_update("eng:set:acctc")
    await callback_query(confirm_update, context)

    assert client.update_settings_calls == [
        {
            "community_id": "community-1",
            "updates": {
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
            },
        }
    ]
    assert "Assigned account:" not in confirm_update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_non_admin_cannot_change_engagement_limits_or_posting_callbacks() -> None:
    client = _FakeApiClient()
    settings = _settings(admin_user_ids=(999,))
    command_update = _message_update()
    callback_update = _callback_update("eng:set:post:community-1:1")
    edit_update = _callback_update("eng:set:e:community-1:mp")
    account_confirm_update = _callback_update("eng:set:acctc")

    await set_engagement_limits_command(
        command_update,
        _context(client, "community-1", "2", "180", settings=settings),
    )
    await callback_query(callback_update, _context(client, settings=settings))
    await callback_query(edit_update, _context(client, settings=settings))
    await callback_query(account_confirm_update, _context(client, settings=settings))

    assert client.get_settings_calls == []
    assert client.update_settings_calls == []
    assert command_update.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )
    assert callback_update.callback_query.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )
    assert edit_update.callback_query.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )
    assert account_confirm_update.callback_query.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )


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
async def test_engagement_rollout_command_renders_aggregate_similarity_bands() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_rollout_command(update, _context(client, "21"))

    assert client.rollout_calls == [{"window_days": 21}]
    message = update.message.replies[0]["text"]
    assert "Semantic rollout | 21 days" in message
    assert "Approval rate: 50%" in message
    assert "0.80-0.89: 1" in message
    assert "Candidate ID" not in message
    assert "Source:" not in message


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
    assert "Good examples: #1 Compare export paths first." in update.message.replies[1]["text"]
    assert "eng:topic:toggle:topic-1:0" in _callback_data_values(
        update.message.replies[1]["reply_markup"]
    )
    assert "eng:topic:open:topic-1" in _callback_data_values(update.message.replies[1]["reply_markup"])
    assert "eng:topic:toggle:topic-2:1" in _callback_data_values(
        update.message.replies[2]["reply_markup"]
    )


@pytest.mark.asyncio
async def test_engagement_topic_command_opens_detail_with_example_controls() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_topic_command(update, _context(client, "topic-1"))

    assert client.get_topic_calls == ["topic-1"]
    text = update.message.replies[0]["text"]
    assert "Topic ID: topic-1" in text
    assert "Bad examples (avoid copying)" in text
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:topic:edit:topic-1:stance_guidance" in callbacks
    assert "eng:topic:rmx:topic-1:g:0" in callbacks


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
async def test_topic_example_commands_mutate_good_and_bad_examples() -> None:
    client = _FakeApiClient()
    good_update = _message_update()
    bad_update = _message_update()

    await topic_good_reply_command(good_update, _context(client, "topic-1", "|", "Lead with tradeoffs."))
    await topic_bad_reply_command(bad_update, _context(client, "topic-1", "|", "Buy now."))

    assert client.add_topic_example_calls == [
        {"topic_id": "topic-1", "example_type": "good", "example": "Lead with tradeoffs."},
        {"topic_id": "topic-1", "example_type": "bad", "example": "Buy now."},
    ]
    assert "Topic example added." in good_update.message.replies[0]["text"]
    assert "Topic example added." in bad_update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_topic_remove_example_command_uses_one_based_operator_index() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await topic_remove_example_command(update, _context(client, "topic-1", "good", "1"))

    assert client.remove_topic_example_calls == [
        {"topic_id": "topic-1", "example_type": "good", "index": 0}
    ]
    assert "Removed good example #1." in update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_topic_keywords_command_updates_selected_keyword_list() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await topic_keywords_command(
        update,
        _context(client, "topic-1", "negative", "jobs,", "recruiting"),
    )

    assert client.update_topic_calls == [
        {
            "topic_id": "topic-1",
            "updates": {"negative_keywords": ["jobs", "recruiting"]},
        }
    ]
    assert "Topic negative keywords updated." in update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_non_admin_cannot_mutate_topics_or_style_rules() -> None:
    client = _FakeApiClient()
    settings = _settings(admin_user_ids=(999,))
    topic_update = _message_update()
    style_update = _callback_update("eng:admin:srt:rule-1:0")

    await topic_keywords_command(
        topic_update,
        _context(client, "topic-1", "negative", "jobs,", "recruiting", settings=settings),
    )
    await callback_query(style_update, _context(client, settings=settings))

    assert client.update_topic_calls == []
    assert client.update_style_rule_calls == []
    assert topic_update.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )
    assert style_update.callback_query.message.replies[0]["text"] == (
        "This engagement admin control is limited to admin operators."
    )


@pytest.mark.asyncio
async def test_edit_topic_guidance_command_starts_guided_edit() -> None:
    client = _FakeApiClient()
    context = _context(client, "topic-1")
    update = _message_update()

    await edit_topic_guidance_command(update, context)

    assert "Editing Topic guidance" in update.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.object_id == "topic-1"
    assert pending.field == "stance_guidance"


@pytest.mark.asyncio
async def test_topic_open_edit_and_remove_callbacks_route_correctly() -> None:
    client = _FakeApiClient()
    open_update = _callback_update("eng:topic:open:topic-1")
    edit_update = _callback_update("eng:topic:edit:topic-1:trigger_keywords")
    add_update = _callback_update("eng:topic:addx:topic-1:g")
    remove_update = _callback_update("eng:topic:rmx:topic-1:b:0")
    context = _context(client)

    await callback_query(open_update, context)
    await callback_query(edit_update, context)
    await callback_query(add_update, context)
    await callback_query(remove_update, context)

    assert client.get_topic_calls[0] == "topic-1"
    assert "Topic ID: topic-1" in open_update.callback_query.message.replies[0]["text"]
    assert "Editing Trigger keywords" in edit_update.callback_query.message.replies[0]["text"]
    assert "Editing Good topic example" in add_update.callback_query.message.replies[0]["text"]
    assert "Removed bad example #1." in remove_update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_topic_example_inline_create_flow_previews_then_saves() -> None:
    client = _FakeApiClient()
    context = _context(client)
    start_update = _callback_update("eng:topic:addx:topic-1:b")
    text_update = _message_update("Never pressure people to buy immediately.")
    save_update = _callback_update("eng:edit:save")

    await callback_query(start_update, context)
    await telegram_entity_text(text_update, context)
    await callback_query(save_update, context)

    assert "Bad topic example" in start_update.callback_query.message.replies[0]["text"]
    assert "Review Bad topic example" in text_update.message.replies[0]["text"]
    assert client.add_topic_example_calls[-1] == {
        "topic_id": "topic-1",
        "example_type": "bad",
        "example": "Never pressure people to buy immediately.",
    }
    assert "Topic example added." in save_update.callback_query.edits[0]["text"]
    assert "Bad examples (avoid copying)" in save_update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_engagement_style_command_lists_scoped_rules_with_actions() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_style_command(update, _context(client, "community", "community-1"))

    assert client.style_list_calls == [
        {"scope_type": "community", "scope_id": "community-1", "limit": 5, "offset": 0}
    ]
    assert "Engagement style rules (1-1 of 1) | community community-1" in update.message.replies[0]["text"]
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:admin:src" in callbacks
    assert "eng:admin:sr:community:community-1:0" in callbacks
    assert "eng:admin:sro:rule-2" in _callback_data_values(update.message.replies[1]["reply_markup"])


@pytest.mark.asyncio
async def test_engagement_style_rule_command_opens_detail() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_style_rule_command(update, _context(client, "rule-1"))

    assert client.get_style_rule_calls == ["rule-1"]
    assert "Rule ID: rule-1" in update.message.replies[0]["text"]
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:admin:sre:rule-1" in callbacks


@pytest.mark.asyncio
async def test_create_edit_and_toggle_style_rule_commands_use_style_rule_routes() -> None:
    client = _FakeApiClient()
    create_update = _message_update()
    edit_update = _message_update()
    toggle_update = _message_update()
    context = _context(client, "global", "-", "|", "Keep", "it", "brief", "|", "50", "|", "Stay", "concise.")

    await create_style_rule_command(create_update, context)
    await edit_style_rule_command(edit_update, _context(client, "rule-1"))
    await toggle_style_rule_command(toggle_update, _context(client, "rule-1", "off"))

    assert client.create_style_rule_calls == [
        {
            "scope_type": "global",
            "scope_id": None,
            "name": "Keep it brief",
            "priority": 50,
            "rule_text": "Stay concise.",
            "created_by": "telegram:123:@operator",
        }
    ]
    assert "Style rule created." in create_update.message.replies[0]["text"]
    assert "Editing Style rule text" in edit_update.message.replies[0]["text"]
    assert client.update_style_rule_calls[-1] == {
        "rule_id": "rule-1",
        "updates": {"active": False, "updated_by": "telegram:123:@operator"},
    }
    assert "Style rule updated." in toggle_update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_style_rule_callbacks_open_edit_toggle_and_create_flow() -> None:
    client = _FakeApiClient()
    open_update = _callback_update("eng:admin:sro:rule-1")
    edit_update = _callback_update("eng:admin:sre:rule-1")
    toggle_update = _callback_update("eng:admin:srt:rule-1:0")
    create_update = _callback_update("eng:admin:src")
    context = _context(client)

    await callback_query(open_update, context)
    await callback_query(edit_update, context)
    await callback_query(toggle_update, context)
    await callback_query(create_update, context)

    assert "Rule ID: rule-1" in open_update.callback_query.message.replies[0]["text"]
    assert "Editing Style rule text" in edit_update.callback_query.message.replies[0]["text"]
    assert "Style rule updated." in toggle_update.callback_query.edits[0]["text"]
    assert "Editing Style rule creation details" in create_update.callback_query.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_style_rule_inline_create_flow_previews_then_saves() -> None:
    client = _FakeApiClient()
    context = _context(client)
    start_update = _callback_update("eng:admin:src")
    text_update = _message_update("global - | Keep it brief | 75 | Stay under three sentences.")
    save_update = _callback_update("eng:edit:save")

    await callback_query(start_update, context)
    await telegram_entity_text(text_update, context)
    await callback_query(save_update, context)

    assert "Review Style rule creation details" in text_update.message.replies[0]["text"]
    assert client.create_style_rule_calls[-1] == {
        "scope_type": "global",
        "scope_id": None,
        "name": "Keep it brief",
        "priority": 75,
        "rule_text": "Stay under three sentences.",
        "created_by": "telegram:123:@operator",
    }
    assert "Style rule created." in save_update.callback_query.edits[0]["text"]


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
async def test_engagement_candidate_command_opens_detail_with_revision_and_edit_controls() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_candidate_command(update, _context(client, "candidate-review"))

    assert client.get_candidate_calls == ["candidate-review"]
    text = update.message.replies[0]["text"]
    assert "Candidate ID: candidate-review" in text
    assert "Source: Discussing CRM tools." in text
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:cand:edit:candidate-review" in callbacks
    assert "eng:cand:rev:candidate-review" in callbacks
    assert "eng:cand:send:candidate-review" not in callbacks


@pytest.mark.asyncio
async def test_candidate_open_and_edit_callbacks_use_detail_and_guided_edit() -> None:
    client = _FakeApiClient()
    open_update = _callback_update("eng:cand:open:candidate-review")
    edit_update = _callback_update("eng:cand:edit:candidate-review")
    context = _context(client)

    await callback_query(open_update, context)
    await callback_query(edit_update, context)

    assert client.get_candidate_calls == ["candidate-review"]
    assert "Candidate ID: candidate-review" in open_update.callback_query.message.replies[0]["text"]
    assert "Editing Final reply" in edit_update.callback_query.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending.object_id == "candidate-review"


@pytest.mark.asyncio
async def test_candidate_revisions_command_lists_revision_history() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await candidate_revisions_command(update, _context(client, "candidate-review"))

    assert client.revision_calls == ["candidate-review"]
    message = update.message.replies[0]["text"]
    assert "Candidate revisions (1)" in message
    assert "Revision 1" in message
    assert "Edited reply text." in message


@pytest.mark.asyncio
async def test_expire_and_retry_candidate_commands_call_candidate_routes() -> None:
    client = _FakeApiClient()
    expire_update = _message_update()
    retry_update = _message_update()

    await expire_candidate_command(expire_update, _context(client, "candidate-review"))
    await retry_candidate_command(retry_update, _context(client, "candidate-failed"))

    assert client.expire_candidate_calls == [
        {"candidate_id": "candidate-review", "expired_by": "telegram:123:@operator"}
    ]
    assert client.retry_candidate_calls == [
        {"candidate_id": "candidate-failed", "retried_by": "telegram:123:@operator"}
    ]
    assert "Candidate expired." in expire_update.message.replies[0]["text"]
    assert "Candidate reopened for review." in retry_update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_expire_and_retry_candidate_callbacks_edit_current_card() -> None:
    client = _FakeApiClient()
    expire_update = _callback_update("eng:cand:exp:candidate-review")
    retry_update = _callback_update("eng:cand:retry:candidate-failed")

    await callback_query(expire_update, _context(client))
    await callback_query(retry_update, _context(client))

    assert "Candidate expired." in expire_update.callback_query.edits[0]["text"]
    assert "Candidate reopened for review." in retry_update.callback_query.edits[0]["text"]


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
