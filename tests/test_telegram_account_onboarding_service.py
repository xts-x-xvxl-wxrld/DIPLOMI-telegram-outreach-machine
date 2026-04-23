from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.core.settings import Settings
from backend.services import telegram_account_onboarding as service


class _FakeClient:
    def __init__(self) -> None:
        self.connected = False
        self.disconnected = False
        self.sent_phone: str | None = None

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    async def send_code_request(self, phone: str) -> SimpleNamespace:
        self.sent_phone = phone
        return SimpleNamespace(phone_code_hash="hash-1")


@pytest.mark.asyncio
async def test_start_telegram_account_onboarding_sends_code_and_uses_safe_session(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient()
    seen_session_paths: list[str] = []

    def fake_telegram_client(session_path, settings):
        seen_session_paths.append(str(session_path))
        return fake_client

    monkeypatch.setattr(service, "_telegram_client", fake_telegram_client)
    settings = Settings(
        TELEGRAM_API_ID="123",
        TELEGRAM_API_HASH="hash",
        SESSIONS_DIR=str(tmp_path),
    )

    result = await service.start_telegram_account_onboarding(
        settings=settings,
        account_pool="engagement",
        phone="+36 20 123 4567",
        session_name="engagement account",
    )

    assert result.status == "code_sent"
    assert result.account_pool == "engagement"
    assert result.session_file_name == "engagement_account.session"
    assert result.phone_code_hash == "hash-1"
    assert fake_client.sent_phone == "+36 20 123 4567"
    assert fake_client.disconnected is True
    assert seen_session_paths == [str(tmp_path / "engagement_account.session")]


@pytest.mark.asyncio
async def test_start_telegram_account_onboarding_requires_api_settings(tmp_path) -> None:
    settings = Settings(TELEGRAM_API_ID="", TELEGRAM_API_HASH="", SESSIONS_DIR=str(tmp_path))

    with pytest.raises(service.AccountOnboardingError, match="TELEGRAM_API_ID"):
        await service.start_telegram_account_onboarding(
            settings=settings,
            account_pool="search",
            phone="+10000000000",
        )
