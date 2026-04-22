# Queue Spec

Top-level routing contract for Redis/RQ background work. Detailed job and operations contracts live in `wiki/spec/queue/`.

## Responsibility

- Represent async work as explicit typed jobs with stable payload contracts.
- Keep workers stateless and persist durable state in Postgres.
- Separate discovery, collection, analysis, and engagement worker boundaries.

## Code Map

- `backend/queue/client.py` - enqueue helpers and payload metadata.
- `backend/workers/` - job implementations.
- `tests/test_queue_payloads.py` - queue contract tests.

## Shards

- [Job Types](queue/job-types.md)
- [Operations](queue/operations.md)
