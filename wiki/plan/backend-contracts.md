# Backend Contracts Plan

## Goal

Create the missing backend contract specs needed before bot and worker implementation:

- `wiki/spec/account-manager.md`
- `wiki/spec/queue.md`
- `wiki/spec/api.md`

Also update existing specs where the new collection-to-analysis contract changes the database or architecture.

## Key Decision

Collection jobs must not pass large raw message batches through Redis.

Instead, collection writes a compact, capped `collection_runs.analysis_input` artifact in Postgres and enqueues analysis with only `collection_run_id`. The analysis job reads that artifact, writes `analysis_summaries`, and the temporary analysis input expires later.

## Locked Foundation Decisions

- Repository layout lives under `backend/`, `bot/`, `alembic/`, and root Docker/config files.
- Alembic migrations are the database source of truth for implementation.
- PostgreSQL status fields use `text`; validation lives in Python enums and Pydantic schemas for MVP.
- Environment variable names are fixed in the architecture spec.
- `collection_runs.analysis_input` uses the JSON envelope defined in the queue spec.

## Work Items

1. Define account acquisition and release semantics.
2. Define RQ queue names, job payloads, chaining, retries, and scheduling.
3. Define REST endpoints consumed by the Telegram bot and worker/debug flows.
4. Add `collection_runs` to the database spec.
5. Update architecture wording so collection enqueues analysis by `collection_run_id`.
6. Update index and log.

## Non-Goals

- No application code implementation in this plan.
- No changes to `wiki/app-high-level.md`.
- No person-level scores or user ranking endpoints.
- No business logic in collection worker.

## Acceptance Criteria

- The three missing specs exist and are linked from `wiki/index.md`.
- Queue spec defines `collection -> analysis` without raw Redis message payloads.
- Account manager spec defines behavior for no accounts, flood waits, stale leases, and banned accounts.
- API spec defines stable request/response contracts for the bot.
- Database spec includes `collection_runs`.
- Architecture spec locks repo layout and runtime configuration names.
- Queue spec defines the initial `analysis_input` JSON envelope.
- Change log records the spec work.
