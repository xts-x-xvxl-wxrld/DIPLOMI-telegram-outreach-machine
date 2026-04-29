from __future__ import annotations

import pytest

from backend.workers.telegram_engagement import (
    EngagementCommunityInaccessible,
    _raise_classified_telethon_send_exception,
)


class ChatWriteForbiddenError(Exception):
    pass


class ChatAdminRequiredError(Exception):
    pass


@pytest.mark.parametrize(
    "exc",
    [
        ChatWriteForbiddenError("You can't write in this chat"),
        ChatAdminRequiredError("Chat admin privileges are required"),
    ],
)
def test_send_permission_errors_are_community_access_blocks(exc: Exception) -> None:
    with pytest.raises(EngagementCommunityInaccessible):
        _raise_classified_telethon_send_exception(exc)
