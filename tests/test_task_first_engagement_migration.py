from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import column, table
from sqlalchemy.dialects import postgresql


def test_single_topic_backfill_query_avoids_uuid_min() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260428_0013_task_first_engagements.py"
    )
    spec = importlib.util.spec_from_file_location("task_first_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    candidates = table(
        "engagement_candidates",
        column("community_id"),
        column("topic_id"),
    )

    compiled = str(
        migration._single_topic_rows_query(candidates).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "min(engagement_candidates.topic_id)" not in compiled
    assert "min(CAST(engagement_candidates.topic_id AS TEXT))" in compiled
