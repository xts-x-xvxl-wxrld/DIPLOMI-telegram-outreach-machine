# Slice 1: Jitter Foundation

Status: implemented.

## Goal

Create the deterministic timing helpers used by delayed sends, collection due times, read receipts,
and warmup reads.

## Scope

- Add a small pure helper module for bounded stable jitter.
- Support integer-second and integer-minute ranges.
- Seed by stable identifiers such as account ID, community ID, candidate ID, purpose, and time
  bucket.
- Keep helpers dependency-light and injectable for workers and tests.
- Centralize hardcoded account-behavior defaults next to the jitter helpers so later slices share
  one source for delay, warmup, collection, read, cadence, and health-refresh constants.

## Code Areas

- `backend/services/engagement_account_behavior.py` for shared helpers and constants.
- `tests/` for deterministic range and distribution tests.

## Acceptance

- Same seed and range always returns the same value.
- Different purpose strings produce different schedules often enough to spread work.
- Invalid ranges fail fast.
- Tests cover send-delay seconds, collection minutes, read minutes, and bucketed jitter.
- Constants match `wiki/spec/engagement/account-behavior.md`.

## Dependencies

None. Build this first.
