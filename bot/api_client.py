from __future__ import annotations

from typing import Any

import httpx

from bot.api_client_accounts import AccountApiClientMixin
from bot.api_client_search import SearchApiClientMixin


class BotApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BotApiClient(AccountApiClientMixin, SearchApiClientMixin):
    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=timeout_seconds,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def create_brief(self, raw_input: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/briefs",
            json={"raw_input": raw_input, "auto_start_discovery": True},
        )

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/jobs/{job_id}")

    async def get_seed_group(self, seed_group_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/seed-groups/{seed_group_id}")

    async def list_seed_group_channels(self, seed_group_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/seed-groups/{seed_group_id}/channels")

    async def list_seed_group_candidates(
        self,
        seed_group_id: str,
        *,
        limit: int = 5,
        offset: int = 0,
        status: str = "candidate",
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/seed-groups/{seed_group_id}/candidates",
            params={"status": status, "limit": limit, "offset": offset},
        )

    async def review_community(self, community_id: str, *, decision: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/communities/{community_id}/review",
            json={"decision": decision, "store_messages": False},
        )

    async def import_seed_csv(self, csv_text: str, *, file_name: str | None = None) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/seed-imports/csv",
            json={"csv_text": csv_text, "file_name": file_name, "requested_by": "telegram_bot"},
        )

    async def submit_telegram_entity(self, handle: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/telegram-entities",
            json={"handle": handle, "requested_by": "telegram_bot"},
        )

    async def get_telegram_entity(self, intake_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/telegram-entities/{intake_id}")

    async def list_seed_groups(self) -> dict[str, Any]:
        return await self._request("GET", "/seed-groups")

    async def start_seed_group_resolution(
        self,
        seed_group_id: str,
        *,
        limit: int = 100,
        retry_failed: bool = False,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/seed-groups/{seed_group_id}/resolve-jobs",
            json={"limit": limit, "retry_failed": retry_failed},
        )

    async def start_seed_group_expansion(
        self,
        seed_group_id: str,
        *,
        brief_id: str | None = None,
        depth: int = 1,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/seed-groups/{seed_group_id}/expansion-jobs",
            json={"brief_id": brief_id, "depth": depth},
        )

    async def get_accounts(self) -> dict[str, Any]:
        return await self._request("GET", "/debug/accounts")

    async def get_operator_capabilities(self, operator_user_id: int | None = None) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/operator/capabilities",
            operator_user_id=operator_user_id,
        )

    async def get_community(self, community_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/communities/{community_id}")

    async def start_snapshot(self, community_id: str, *, window_days: int = 90) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/communities/{community_id}/snapshot-jobs",
            json={"window_days": window_days},
        )

    async def list_snapshot_runs(self, community_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/communities/{community_id}/snapshot-runs")

    async def list_community_members(
        self,
        community_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        username_present: bool | None = None,
        activity_status: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if username_present is not None:
            params["username_present"] = str(username_present).lower()
        if activity_status is not None:
            params["activity_status"] = activity_status
        return await self._request(
            "GET",
            f"/communities/{community_id}/members",
            params=params,
        )

    async def list_engagement_candidates(
        self,
        *,
        status: str = "needs_review",
        community_id: str | None = None,
        topic_id: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, object] = {"status": status, "limit": limit, "offset": offset}
        if community_id is not None:
            params["community_id"] = community_id
        if topic_id is not None:
            params["topic_id"] = topic_id
        return await self._request(
            "GET",
            "/engagement/candidates",
            params=params,
        )

    async def get_engagement_candidate(self, candidate_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/candidates/{candidate_id}")

    async def list_engagement_candidate_revisions(self, candidate_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/candidates/{candidate_id}/revisions")

    async def get_engagement_cockpit_home(self) -> dict[str, Any]:
        return await self._request("GET", "/engagement/cockpit/home")

    async def get_engagement_cockpit_approvals(self) -> dict[str, Any]:
        return await self._request("GET", "/engagement/cockpit/approvals")

    async def get_engagement_cockpit_approvals_for_engagement(self, engagement_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/engagement/cockpit/engagements/{engagement_id}/approvals",
        )

    async def approve_engagement_cockpit_draft(self, draft_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/engagement/cockpit/drafts/{draft_id}/approve")

    async def reject_engagement_cockpit_draft(self, draft_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/engagement/cockpit/drafts/{draft_id}/reject")

    async def edit_engagement_cockpit_draft(
        self,
        draft_id: str,
        *,
        edit_request: str,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"edit_request": edit_request}
        if requested_by is not None:
            payload["requested_by"] = requested_by
        return await self._request(
            "POST",
            f"/engagement/cockpit/drafts/{draft_id}/edit",
            json=payload,
        )

    async def get_engagement_cockpit_issues(self) -> dict[str, Any]:
        return await self._request("GET", "/engagement/cockpit/issues")

    async def get_engagement_cockpit_issues_for_engagement(self, engagement_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/engagement/cockpit/engagements/{engagement_id}/issues",
        )

    async def act_on_engagement_cockpit_issue(self, issue_id: str, *, action_key: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/engagement/cockpit/issues/{issue_id}/actions/{action_key}",
        )

    async def get_engagement_cockpit_issue_rate_limit(self, issue_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/cockpit/issues/{issue_id}/rate-limit")

    async def get_engagement_cockpit_quiet_hours(self, engagement_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/engagement/cockpit/engagements/{engagement_id}/quiet-hours",
        )

    async def update_engagement_cockpit_quiet_hours(
        self,
        engagement_id: str,
        *,
        quiet_hours_enabled: bool,
        quiet_hours_start: str | None = None,
        quiet_hours_end: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"quiet_hours_enabled": quiet_hours_enabled}
        if quiet_hours_start is not None:
            payload["quiet_hours_start"] = quiet_hours_start
        if quiet_hours_end is not None:
            payload["quiet_hours_end"] = quiet_hours_end
        return await self._request(
            "PUT",
            f"/engagement/cockpit/engagements/{engagement_id}/quiet-hours",
            json=payload,
        )

    async def list_engagement_cockpit_engagements(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/engagement/cockpit/engagements",
            params={"limit": limit, "offset": offset},
        )

    async def get_engagement_cockpit_engagement(self, engagement_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/cockpit/engagements/{engagement_id}")

    async def list_engagement_cockpit_sent(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/engagement/cockpit/sent",
            params={"limit": limit, "offset": offset},
        )

    async def list_engagement_targets(
        self,
        *,
        status: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        return await self._request("GET", "/engagement/targets", params=params)

    async def get_engagement_target(self, target_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/targets/{target_id}")

    async def create_engagement_target(
        self,
        *,
        target_ref: str,
        added_by: str,
        notes: str | None = None,
        operator_user_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"target_ref": target_ref, "added_by": added_by}
        if notes is not None:
            payload["notes"] = notes
        return await self._request(
            "POST",
            "/engagement/targets",
            json=payload,
            operator_user_id=operator_user_id,
        )

    async def update_engagement_target(
        self,
        target_id: str,
        operator_user_id: int | None = None,
        **updates: Any,
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/engagement/targets/{target_id}",
            json=updates,
            operator_user_id=operator_user_id,
        )

    async def resolve_engagement_target(
        self,
        target_id: str,
        *,
        requested_by: str | None = None,
        operator_user_id: int | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/engagement/targets/{target_id}/resolve-jobs",
            json={"requested_by": requested_by},
            operator_user_id=operator_user_id,
        )

    async def start_engagement_target_join(
        self,
        target_id: str,
        *,
        telegram_account_id: str | None = None,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/engagement/targets/{target_id}/join-jobs",
            json={
                "telegram_account_id": telegram_account_id,
                "requested_by": requested_by,
            },
        )

    async def start_engagement_target_collection(
        self,
        target_id: str,
        *,
        window_days: int = 90,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/engagement/targets/{target_id}/collection-jobs",
            json={
                "window_days": window_days,
                "requested_by": requested_by,
            },
        )

    async def list_engagement_target_collection_runs(self, target_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/targets/{target_id}/collection-runs")

    async def start_engagement_target_detection(
        self,
        target_id: str,
        *,
        window_minutes: int = 60,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/engagement/targets/{target_id}/detect-jobs",
            json={
                "window_minutes": window_minutes,
                "requested_by": requested_by,
            },
        )

    async def approve_engagement_candidate(
        self,
        candidate_id: str,
        *,
        reviewed_by: str,
        final_reply: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"reviewed_by": reviewed_by}
        if final_reply is not None:
            payload["final_reply"] = final_reply
        return await self._request(
            "POST",
            f"/engagement/candidates/{candidate_id}/approve",
            json=payload,
        )

    async def reject_engagement_candidate(
        self,
        candidate_id: str,
        *,
        reviewed_by: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"reviewed_by": reviewed_by}
        if reason is not None:
            payload["reason"] = reason
        return await self._request(
            "POST",
            f"/engagement/candidates/{candidate_id}/reject",
            json=payload,
        )

    async def send_engagement_candidate(
        self,
        candidate_id: str,
        *,
        approved_by: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if approved_by is not None:
            payload["approved_by"] = approved_by
        return await self._request(
            "POST",
            f"/engagement/candidates/{candidate_id}/send-jobs",
            json=payload,
        )

    async def get_engagement_settings(self, community_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/communities/{community_id}/engagement-settings",
        )

    async def update_engagement_settings(
        self,
        community_id: str,
        *,
        mode: str,
        allow_join: bool = False,
        allow_post: bool = False,
        reply_only: bool = True,
        require_approval: bool = True,
        max_posts_per_day: int = 1,
        min_minutes_between_posts: int = 240,
        quiet_hours_start: str | None = None,
        quiet_hours_end: str | None = None,
        assigned_account_id: str | None = None,
        operator_user_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": mode,
            "allow_join": allow_join,
            "allow_post": allow_post,
            "reply_only": reply_only,
            "require_approval": require_approval,
            "max_posts_per_day": max_posts_per_day,
            "min_minutes_between_posts": min_minutes_between_posts,
            "quiet_hours_start": quiet_hours_start,
            "quiet_hours_end": quiet_hours_end,
            "assigned_account_id": assigned_account_id,
        }
        return await self._request(
            "PUT",
            f"/communities/{community_id}/engagement-settings",
            json=payload,
            operator_user_id=operator_user_id,
        )

    async def list_engagement_topics(self) -> dict[str, Any]:
        return await self._request("GET", "/engagement/topics")

    async def get_engagement_topic(self, topic_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/topics/{topic_id}")

    async def create_engagement_topic(
        self,
        *,
        name: str,
        stance_guidance: str,
        trigger_keywords: list[str],
        description: str | None = None,
        negative_keywords: list[str] | None = None,
        example_good_replies: list[str] | None = None,
        example_bad_replies: list[str] | None = None,
        active: bool = True,
        operator_user_id: int | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/engagement/topics",
            json={
                "name": name,
                "description": description,
                "stance_guidance": stance_guidance,
                "trigger_keywords": trigger_keywords,
                "negative_keywords": negative_keywords or [],
                "example_good_replies": example_good_replies or [],
                "example_bad_replies": example_bad_replies or [],
                "active": active,
            },
            operator_user_id=operator_user_id,
        )

    async def update_engagement_topic(
        self,
        topic_id: str,
        operator_user_id: int | None = None,
        **updates: Any,
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/engagement/topics/{topic_id}",
            json=updates,
            operator_user_id=operator_user_id,
        )

    async def add_engagement_topic_example(
        self,
        topic_id: str,
        *,
        example_type: str,
        example: str,
        operator_user_id: int | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/engagement/topics/{topic_id}/examples",
            json={"example_type": example_type, "example": example},
            operator_user_id=operator_user_id,
        )

    async def remove_engagement_topic_example(
        self,
        topic_id: str,
        *,
        example_type: str,
        index: int,
        operator_user_id: int | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"/engagement/topics/{topic_id}/examples/{example_type}/{index}",
            operator_user_id=operator_user_id,
        )

    async def list_engagement_prompt_profiles(
        self,
        *,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/engagement/prompt-profiles",
            params={"limit": limit, "offset": offset},
        )

    async def get_engagement_prompt_profile(self, profile_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/prompt-profiles/{profile_id}")

    async def create_engagement_prompt_profile(
        self,
        operator_user_id: int | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/engagement/prompt-profiles",
            json=payload,
            operator_user_id=operator_user_id,
        )

    async def update_engagement_prompt_profile(
        self,
        profile_id: str,
        operator_user_id: int | None = None,
        **updates: Any,
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/engagement/prompt-profiles/{profile_id}",
            json=updates,
            operator_user_id=operator_user_id,
        )

    async def activate_engagement_prompt_profile(
        self,
        profile_id: str,
        *,
        updated_by: str | None = None,
        operator_user_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if updated_by is not None:
            payload["updated_by"] = updated_by
        return await self._request(
            "POST",
            f"/engagement/prompt-profiles/{profile_id}/activate",
            json=payload,
            operator_user_id=operator_user_id,
        )

    async def duplicate_engagement_prompt_profile(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        created_by: str | None = None,
        operator_user_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if created_by is not None:
            payload["created_by"] = created_by
        return await self._request(
            "POST",
            f"/engagement/prompt-profiles/{profile_id}/duplicate",
            json=payload,
            operator_user_id=operator_user_id,
        )

    async def rollback_engagement_prompt_profile(
        self,
        profile_id: str,
        *,
        version_id: str,
        updated_by: str | None = None,
        operator_user_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"version_id": version_id}
        if updated_by is not None:
            payload["updated_by"] = updated_by
        return await self._request(
            "POST",
            f"/engagement/prompt-profiles/{profile_id}/rollback",
            json=payload,
            operator_user_id=operator_user_id,
        )

    async def preview_engagement_prompt_profile(
        self,
        profile_id: str,
        *,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/engagement/prompt-profiles/{profile_id}/preview",
            json={"variables": variables},
        )

    async def list_engagement_prompt_profile_versions(self, profile_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/prompt-profiles/{profile_id}/versions")

    async def list_engagement_style_rules(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        active: bool | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if scope_type is not None:
            params["scope_type"] = scope_type
        if scope_id is not None:
            params["scope_id"] = scope_id
        if active is not None:
            params["active"] = str(active).lower()
        return await self._request("GET", "/engagement/style-rules", params=params)

    async def get_engagement_style_rule(self, rule_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/style-rules/{rule_id}")

    async def create_engagement_style_rule(
        self,
        operator_user_id: int | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/engagement/style-rules",
            json=payload,
            operator_user_id=operator_user_id,
        )

    async def update_engagement_style_rule(
        self,
        rule_id: str,
        operator_user_id: int | None = None,
        **updates: Any,
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/engagement/style-rules/{rule_id}",
            json=updates,
            operator_user_id=operator_user_id,
        )

    async def edit_engagement_candidate(
        self,
        candidate_id: str,
        *,
        final_reply: str,
        edited_by: str,
        edit_reason: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"final_reply": final_reply, "edited_by": edited_by}
        if edit_reason is not None:
            payload["edit_reason"] = edit_reason
        return await self._request(
            "POST",
            f"/engagement/candidates/{candidate_id}/edit",
            json=payload,
        )

    async def expire_engagement_candidate(
        self,
        candidate_id: str,
        *,
        expired_by: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if expired_by is not None:
            payload["expired_by"] = expired_by
        return await self._request(
            "POST",
            f"/engagement/candidates/{candidate_id}/expire",
            json=payload,
        )

    async def retry_engagement_candidate(
        self,
        candidate_id: str,
        *,
        retried_by: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if retried_by is not None:
            payload["retried_by"] = retried_by
        return await self._request(
            "POST",
            f"/engagement/candidates/{candidate_id}/retry",
            json=payload,
        )

    async def start_community_join(
        self,
        community_id: str,
        *,
        telegram_account_id: str | None = None,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/communities/{community_id}/join-jobs",
            json={
                "telegram_account_id": telegram_account_id,
                "requested_by": requested_by,
            },
        )

    async def start_engagement_detection(
        self,
        community_id: str,
        *,
        window_minutes: int = 60,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/communities/{community_id}/engagement-detect-jobs",
            json={
                "window_minutes": window_minutes,
                "requested_by": requested_by,
            },
        )

    async def list_engagement_actions(
        self,
        *,
        community_id: str | None = None,
        candidate_id: str | None = None,
        status: str | None = None,
        action_type: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if community_id is not None:
            params["community_id"] = community_id
        if candidate_id is not None:
            params["candidate_id"] = candidate_id
        if status is not None:
            params["status"] = status
        if action_type is not None:
            params["action_type"] = action_type
        return await self._request("GET", "/engagement/actions", params=params)

    async def get_engagement_semantic_rollout(
        self,
        *,
        window_days: int = 14,
        community_id: str | None = None,
        topic_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, object] = {"window_days": window_days}
        if community_id is not None:
            params["community_id"] = community_id
        if topic_id is not None:
            params["topic_id"] = topic_id
        return await self._request("GET", "/engagement/semantic-rollout", params=params)

    async def create_engagement(
        self,
        *,
        target_id: str,
        created_by: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/engagements",
            json={"target_id": target_id, "created_by": created_by},
        )

    async def patch_engagement(
        self,
        engagement_id: str,
        *,
        topic_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if topic_id is not None:
            payload["topic_id"] = topic_id
        if name is not None:
            payload["name"] = name
        return await self._request(
            "PATCH",
            f"/api/engagements/{engagement_id}",
            json=payload,
        )

    async def put_engagement_settings(
        self,
        engagement_id: str,
        *,
        assigned_account_id: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if assigned_account_id is not None:
            payload["assigned_account_id"] = assigned_account_id
        if mode is not None:
            payload["mode"] = mode
        return await self._request(
            "PUT",
            f"/api/engagements/{engagement_id}/settings",
            json=payload,
        )

    async def wizard_confirm_engagement(
        self,
        engagement_id: str,
        *,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if requested_by is not None:
            payload["requested_by"] = requested_by
        return await self._request(
            "POST",
            f"/api/engagements/{engagement_id}/wizard-confirm",
            json=payload,
        )

    async def wizard_retry_engagement(
        self,
        engagement_id: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/engagements/{engagement_id}/wizard-retry",
            json={},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        operator_user_id: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if operator_user_id is not None:
            headers = dict(kwargs.pop("headers", {}) or {})
            headers["X-Telegram-User-Id"] = str(operator_user_id)
            kwargs["headers"] = headers
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise BotApiError(f"API request failed: {exc}") from exc

        if response.status_code >= 400:
            raise BotApiError(
                _extract_error_message(response),
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise BotApiError("API returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise BotApiError("API returned an unexpected response")
        return data


def _extract_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text or f"API returned HTTP {response.status_code}"

    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str):
            return message
    if isinstance(detail, str):
        return detail
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
    return f"API returned HTTP {response.status_code}"
