# Database Spec

Top-level routing contract for Postgres schema design. Table details live in `wiki/spec/database/` shards.

## Responsibility

- Use Alembic migrations as implementation source of truth.
- Preserve seed-first provenance and community-level analysis boundaries.
- Keep engagement tables separated from discovery collection concerns.

## Code Map

- `backend/db/models.py` - SQLAlchemy model definitions.
- `alembic/versions/` - schema migrations.
- `tests/test_*_schema.py` - schema regression tests.

## Shards

- [Foundation](database/foundation.md)
- [Search Tables](database/search.md)
- [Engagement Tables](database/engagement.md)
- [Indexes and Pipeline](database/indexes-pipeline.md)
