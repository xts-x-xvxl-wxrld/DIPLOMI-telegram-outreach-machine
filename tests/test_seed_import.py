from __future__ import annotations

import pytest

from backend.services.seed_import import normalize_telegram_seed


@pytest.mark.parametrize(
    ("raw_value", "username"),
    [
        ("@founder_circle", "founder_circle"),
        ("https://t.me/founder_circle", "founder_circle"),
        ("t.me/s/founder_circle", "founder_circle"),
    ],
)
def test_normalize_telegram_seed_accepts_public_channel_forms(
    raw_value: str,
    username: str,
) -> None:
    seed = normalize_telegram_seed(raw_value)

    assert seed.username == username
    assert seed.normalized_key == f"username:{username}"
    assert seed.telegram_url == f"https://t.me/{username}"


def test_normalize_telegram_seed_rejects_private_invite_links() -> None:
    with pytest.raises(ValueError, match="Private invite"):
        normalize_telegram_seed("https://t.me/+abc123")
