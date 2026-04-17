from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def append_bridge_message(
    inbox_path: str,
    *,
    chat_id: int | None,
    user_id: int | None,
    username: str | None,
    text: str,
    source: str = "telegram",
) -> dict[str, object]:
    record: dict[str, object] = {
        "id": uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "chat_id": chat_id,
        "user_id": user_id,
        "username": username,
        "text": text,
    }

    path = Path(inbox_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=True, sort_keys=True))
        file.write("\n")

    return record


def read_bridge_messages(inbox_path: str, *, limit: int = 10) -> list[dict[str, object]]:
    path = Path(inbox_path)
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    messages: list[dict[str, object]] = []
    for line in lines[-limit:]:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            messages.append(value)
    return messages
