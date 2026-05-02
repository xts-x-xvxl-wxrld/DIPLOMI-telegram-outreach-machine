from __future__ import annotations

from typing import Any, Protocol


class _EngagementAdminRequestClient(Protocol):
    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        ...


class EngagementAdminApiClientMixin:
    async def list_engagement_topics(self: _EngagementAdminRequestClient) -> dict[str, Any]:
        return await self._request("GET", "/engagement/topics")

    async def get_engagement_topic(
        self: _EngagementAdminRequestClient,
        topic_id: str,
    ) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/topics/{topic_id}")

    async def create_engagement_topic(
        self: _EngagementAdminRequestClient,
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
        self: _EngagementAdminRequestClient,
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
        self: _EngagementAdminRequestClient,
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
        self: _EngagementAdminRequestClient,
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
        self: _EngagementAdminRequestClient,
        *,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/engagement/prompt-profiles",
            params={"limit": limit, "offset": offset},
        )

    async def get_engagement_prompt_profile(
        self: _EngagementAdminRequestClient,
        profile_id: str,
    ) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/prompt-profiles/{profile_id}")

    async def create_engagement_prompt_profile(
        self: _EngagementAdminRequestClient,
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
        self: _EngagementAdminRequestClient,
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
        self: _EngagementAdminRequestClient,
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
        self: _EngagementAdminRequestClient,
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
        self: _EngagementAdminRequestClient,
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
        self: _EngagementAdminRequestClient,
        profile_id: str,
        *,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/engagement/prompt-profiles/{profile_id}/preview",
            json={"variables": variables},
        )

    async def list_engagement_prompt_profile_versions(
        self: _EngagementAdminRequestClient,
        profile_id: str,
    ) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/prompt-profiles/{profile_id}/versions")

    async def list_engagement_style_rules(
        self: _EngagementAdminRequestClient,
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

    async def get_engagement_style_rule(
        self: _EngagementAdminRequestClient,
        rule_id: str,
    ) -> dict[str, Any]:
        return await self._request("GET", f"/engagement/style-rules/{rule_id}")

    async def create_engagement_style_rule(
        self: _EngagementAdminRequestClient,
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
        self: _EngagementAdminRequestClient,
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

    async def create_engagement(
        self: _EngagementAdminRequestClient,
        *,
        target_id: str,
        created_by: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/engagements",
            json={"target_id": target_id, "created_by": created_by},
        )

    async def patch_engagement(
        self: _EngagementAdminRequestClient,
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
            f"/engagements/{engagement_id}",
            json=payload,
        )

    async def put_engagement_settings(
        self: _EngagementAdminRequestClient,
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
            f"/engagements/{engagement_id}/settings",
            json=payload,
        )

    async def wizard_confirm_engagement(
        self: _EngagementAdminRequestClient,
        engagement_id: str,
        *,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if requested_by is not None:
            payload["requested_by"] = requested_by
        return await self._request(
            "POST",
            f"/engagements/{engagement_id}/wizard-confirm",
            json=payload,
        )

    async def wizard_retry_engagement(
        self: _EngagementAdminRequestClient,
        engagement_id: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/engagements/{engagement_id}/wizard-retry",
            json={},
        )


__all__ = ["EngagementAdminApiClientMixin"]
