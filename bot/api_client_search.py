from __future__ import annotations

from typing import Any, Protocol


class _SearchRequestClient(Protocol):
    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        ...


class SearchApiClientMixin:
    async def create_search_run(
        self: _SearchRequestClient,
        query: str,
        *,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/search-runs",
            json={
                "query": query,
                "requested_by": requested_by,
                "enabled_adapters": ["telegram_entity_search"],
            },
        )

    async def list_search_runs(
        self: _SearchRequestClient,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/search-runs",
            params={"limit": limit, "offset": offset},
        )

    async def get_search_run(self: _SearchRequestClient, search_run_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/search-runs/{search_run_id}")

    async def list_search_run_queries(
        self: _SearchRequestClient,
        search_run_id: str,
    ) -> dict[str, Any]:
        return await self._request("GET", f"/search-runs/{search_run_id}/queries")

    async def list_search_candidates(
        self: _SearchRequestClient,
        search_run_id: str,
        *,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/search-runs/{search_run_id}/candidates",
            params={"limit": limit, "offset": offset},
        )

    async def review_search_candidate(
        self: _SearchRequestClient,
        candidate_id: str,
        *,
        action: str,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/search-candidates/{candidate_id}/review",
            json={"action": action, "requested_by": requested_by},
        )

    async def convert_search_candidate_to_seed(
        self: _SearchRequestClient,
        candidate_id: str,
        *,
        seed_group_name: str | None = None,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/search-candidates/{candidate_id}/convert-to-seed",
            json={"seed_group_name": seed_group_name, "requested_by": requested_by},
        )

    async def start_search_rerank(
        self: _SearchRequestClient,
        search_run_id: str,
    ) -> dict[str, Any]:
        return await self._request("POST", f"/search-runs/{search_run_id}/rerank-jobs")


__all__ = ["SearchApiClientMixin"]
