# Slice 4: Opportunity Cadence

## Goal

Rate-limit started root opportunities while allowing tightly bounded direct continuations.

## Scope

- Add root/continuation classification for reply opportunities.
- Classify a continuation only when the source message directly replies to a Telegram message sent
  by the selected managed engagement account in the same community.
- Count queued and sent root opportunities against account-level start caps.
- Add continuation-specific per-root caps and spacing.
- Treat unproven continuation candidates as root opportunities.
- Prefer a migration for durable candidate fields before exposing continuation behavior in the bot.

## Code Areas

- `backend/db/models_engagement.py`
- Alembic migration for optional durable candidate fields.
- `backend/services/community_engagement_candidates.py`
- `backend/workers/engagement_detect_selection.py`
- `backend/workers/engagement_send.py`
- `tests/test_engagement_schema.py`
- `tests/test_engagement_detect_worker.py`
- `tests/test_engagement_send_worker.py`

## Acceptance

- Root opportunities count against 4-hour, 24-hour, minimum-spacing, and same-community cooldown
  limits when queued or sent.
- Direct continuations bypass root-start caps.
- Continuations still require approval, source preflight, health, membership, idempotency, and
  continuation caps.
- Semantic continuation detection is not implemented in this slice.
- Existing candidates backfill as root opportunities.

## Dependencies

Requires Slice 3 for reliable source-message and sent-message handling.
