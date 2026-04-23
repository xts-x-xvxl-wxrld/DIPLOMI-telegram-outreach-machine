from __future__ import annotations

from typing import Any


class AccountApiClientMixin:
    async def start_account_onboarding(
        self,
        *,
        account_pool: str,
        phone: str,
        session_name: str | None = None,
        notes: str | None = None,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/telegram-accounts/onboarding/start",
            json={
                "account_pool": account_pool,
                "phone": phone,
                "session_name": session_name,
                "notes": notes,
                "requested_by": requested_by,
            },
        )

    async def complete_account_onboarding(
        self,
        *,
        account_pool: str,
        phone: str,
        session_name: str,
        phone_code_hash: str,
        code: str,
        password: str | None = None,
        notes: str | None = None,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/telegram-accounts/onboarding/complete",
            json={
                "account_pool": account_pool,
                "phone": phone,
                "session_name": session_name,
                "phone_code_hash": phone_code_hash,
                "code": code,
                "password": password,
                "notes": notes,
                "requested_by": requested_by,
            },
        )
