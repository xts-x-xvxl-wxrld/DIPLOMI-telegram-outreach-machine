# Engagement API And Bot Compat Note

Legacy/compat API and bot notes that still matter while older engagement
surfaces remain in code.

## Not The Source Of Truth

- Active task-first API behavior lives in `wiki/spec/api/engagement.md`.
- Active task-first bot behavior lives in
  `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`.
- This file should not restate live task-first endpoints, callbacks, DTOs, or
  screen contracts.

## What Still Matters Here

- Older community-scoped settings, topic, target, candidate, and action routes
  still exist in code during migration/compat cleanup.
- The remaining intentional compat/manual bot layer is callback-first:
  `eng:set:*`, `eng:join:*`, `eng:detect:*`, and `eng:actions:*`.
- Operator copy should prefer `reply opportunity` while implementation-facing
  code may still use `candidate` until the rename is fully retired.
- API and bot payloads must not expose phone numbers or person-level scores.

## Compat Code Anchors

- `backend/api/routes/engagement.py`
- `backend/api/routes/engagement_settings_topics.py`
- `backend/api/routes/engagement_targets.py`
- `backend/api/routes/engagement_candidates_actions.py`
- `backend/services/community_engagement_*.py`
- `bot/engagement_commands_*.py`
- `bot/ui_engagement.py`
- `bot/callback_handlers.py`

## Cleanup Rule

Do not add new task-first contract detail here. Either point to the canonical
task-first docs or remove the compat note once the remaining legacy surfaces are
gone.
