# Slice 5: Post-Join Acclimation

## Goal

Avoid immediate post-join sending and give the selected engagement account a short
warmup period while still allowing operators to review newly drafted replies.

## Scope

- After successful join, read the latest visible messages up to the configured limit.
- Best-effort mark that initial batch as read when Telegram allows it.
- Block sending while the selected joined membership is inside the 60-minute warmup window.
- Let detection keep drafting opportunities during warmup so review can begin before posting is
  allowed.
- Add explicit skip reasons for missing membership, missing `joined_at`, and active warmup on the
  send path.

## Code Areas

- `backend/workers/community_join.py`
- `backend/workers/telegram_engagement.py`
- `backend/workers/engagement_detect_process.py`
- `backend/workers/engagement_send.py`
- `tests/test_collection_worker.py`
- `tests/test_engagement_detect_worker.py`
- `tests/test_engagement_send_worker.py`
- `tests/test_telegram_engagement_adapter.py`

## Acceptance

- Successful join performs one bounded best-effort initial read.
- Send skips memberships still inside warmup.
- Detection can still create drafts during warmup.
- Warmup does not alter existing join audit semantics.

## Dependencies

Can follow Slice 1. Pairs well with Slice 7 for ongoing read cadence.
