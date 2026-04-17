from __future__ import annotations

import json

from bot.bridge import append_bridge_message, read_bridge_messages
from scripts.telegram_bridge_send import build_bridge_text


def test_append_bridge_message_writes_jsonl_record(tmp_path) -> None:
    inbox_path = tmp_path / "bridge" / "inbox.jsonl"

    record = append_bridge_message(
        str(inbox_path),
        chat_id=123,
        user_id=456,
        username="operator",
        text="hello from telegram",
    )

    assert record["id"]
    lines = inbox_path.read_text(encoding="utf-8").splitlines()
    saved = json.loads(lines[0])
    assert saved["chat_id"] == 123
    assert saved["user_id"] == 456
    assert saved["username"] == "operator"
    assert saved["text"] == "hello from telegram"


def test_read_bridge_messages_returns_tail_and_skips_bad_lines(tmp_path) -> None:
    inbox_path = tmp_path / "inbox.jsonl"
    inbox_path.write_text(
        "\n".join(
            [
                json.dumps({"id": "one", "text": "first"}),
                "not-json",
                json.dumps({"id": "two", "text": "second"}),
            ]
        ),
        encoding="utf-8",
    )

    messages = read_bridge_messages(str(inbox_path), limit=3)

    assert messages == [
        {"id": "one", "text": "first"},
        {"id": "two", "text": "second"},
    ]


def test_build_bridge_text_labels_sender() -> None:
    assert build_bridge_text("codex", "done") == "codex:\ndone"
