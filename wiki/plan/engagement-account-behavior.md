# Engagement Account Behavior

Status: planned.

## Goal

Implement hardcoded natural account behavior for engagement accounts without adding operator-facing
controls in the first version.

## Decisions

- Use Redis/RQ delayed scheduling for approved send delay. Do not hold worker slots with sleep.
- Use Redis due-state for per-community collection and per-account/community read acknowledgements.
- Use `community_account_memberships.joined_at` for the first post-join acclimation gate.
- Count started root opportunities, not continuation replies, against account-level cadence caps.
- Treat only direct replies to a managed account's previously sent Telegram message as MVP
  continuations.
- Keep collection free of engagement business logic except adapter-level read acknowledgement hooks.

## Slices

- [Slice 1: Jitter Foundation](engagement-account-behavior/01-jitter-foundation.md) - pure
  stable-jitter helpers and tests.
- [Slice 2: Delayed Send Queueing](engagement-account-behavior/02-delayed-send-queueing.md) -
  Redis/RQ delayed send scheduling without worker sleep.
- [Slice 3: Send Source Preflight](engagement-account-behavior/03-send-source-preflight.md) -
  source-message accessibility/replyability checks before Telegram sends.
- [Slice 4: Opportunity Cadence](engagement-account-behavior/04-opportunity-cadence.md) - root
  opportunity counting and direct-continuation handling.
- [Slice 5: Post-Join Acclimation](engagement-account-behavior/05-post-join-acclimation.md) -
  initial reads and warmup gates for detection and sending.
- [Slice 6: Jittered Collection](engagement-account-behavior/06-jittered-collection.md) -
  per-community Redis due times for active engagement collection.
- [Slice 7: Jittered Read Receipts](engagement-account-behavior/07-jittered-read-receipts.md) -
  per-account/community read acknowledgement cadence.
- [Slice 8: Account Health Refresh](engagement-account-behavior/08-account-health-refresh.md) -
  scheduled Telegram account health checks and status mapping.

## Acceptance

- Approved sends are delayed through Redis/RQ scheduling and do not block worker slots while waiting.
- Re-running approval for the same candidate cannot create duplicate delayed send jobs.
- Send workers still skip stale, unapproved, non-replyable, over-limit, or unhealthy-account sends.
- New root opportunities observe account-level 4-hour, 24-hour, minimum-spacing, and same-community
  cooldown limits.
- Direct continuations bypass root opportunity caps but remain approval-gated and capped per root.
- Detection and sending ignore memberships still inside the post-join warmup window.
- Active engagement collection is spread by per-community due time instead of one global cadence.
- Read acknowledgements are jittered per account/community and are best effort.
- Account health refresh maps Telegram auth, ban, and FloodWait states to deterministic account
  statuses.
- `python scripts/check_fragmentation.py`, `ruff check .`, and `pytest -q` pass before branch merge.
