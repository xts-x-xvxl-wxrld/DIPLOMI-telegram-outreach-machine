from __future__ import annotations

import json
import re
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "engagement_semantic_eval.jsonl"
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
FORBIDDEN_KEYS = {
    "sender_username",
    "sender_user_id",
    "telegram_user_id",
    "phone",
    "person_score",
    "lead_score",
}


def test_engagement_semantic_eval_fixture_is_sanitized_and_labeled() -> None:
    rows = [
        json.loads(line)
        for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert rows
    assert {row["human_label"] for row in rows} == {"match", "no_match"}
    assert all(row["detector_decision"] in {"engage", "skip"} for row in rows)

    for row in rows:
        assert set(row).isdisjoint(FORBIDDEN_KEYS)
        assert row["fixture_id"]
        assert row["topic_profile"].strip()
        assert row["sanitized_message_text"].strip()
        assert row["human_label"] in {"match", "no_match"}
        assert 0.0 <= float(row["similarity_score"]) <= 1.0

        rendered = json.dumps(row, ensure_ascii=True).casefold()
        assert "@" not in rendered
        assert "person-level score" not in rendered
        assert "lead score" not in rendered
        assert PHONE_RE.search(rendered) is None
