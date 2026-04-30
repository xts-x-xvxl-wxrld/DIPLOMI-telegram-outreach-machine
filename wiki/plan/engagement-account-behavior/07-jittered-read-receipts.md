# Slice 7: Jittered Read Receipts

## Goal

Mark engagement messages read on a per-account/community rhythm instead of acknowledging every
collection poll.

## Scope

- Store read due times under `engagement:read:next:{telegram_account_id}:{community_id}`.
- Add adapter-level read acknowledgement hooks usable by collection.
- Mark read only when new messages exist and the pair is due.
- Schedule the next read acknowledgement with 1-15 minute stable jitter.
- Cap warmup read checks.
- Store due times as UTC epoch seconds, using the same Redis helper as Slice 6.

## Code Areas

- `backend/workers/collection.py`
- `backend/workers/telegram_collection.py`
- `backend/workers/telegram_engagement.py`
- Redis state helper introduced in Slice 6, if present.
- `tests/test_collection_worker.py`
- `tests/test_telegram_engagement_adapter.py`

## Acceptance

- Collection can call a read acknowledgement hook without owning engagement decision logic.
- Not-due account/community pairs do not mark read.
- Due pairs with new messages mark read best effort and schedule the next due time.
- Read acknowledgement failures do not fail collection.
- Redis outages skip read acknowledgement for that poll and leave collection successful.

## Dependencies

Requires Slice 1. Prefer after Slice 6 if it introduces shared Redis due-state helpers.
