from __future__ import annotations

from typing import Any

import httpx


class BotApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BotApiClient:
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

    async def get_community(self, community_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/communities/{community_id}")

    async def start_collection(self, community_id: str, *, window_days: int = 90) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/communities/{community_id}/collection-jobs",
            json={"window_days": window_days},
        )

    async def list_collection_runs(self, community_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/communities/{community_id}/collection-runs")

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

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
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
