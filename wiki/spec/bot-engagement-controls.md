# Bot Engagement Controls Spec

Legacy/compat overview for older Telegram-native engagement admin and
candidate-review controls.

## Purpose

Keep a short pointer for the legacy/compat engagement-control surfaces that
still exist in code, without letting this doc compete with the task-first
cockpit contract.

## Not The Source Of Truth

- Do not use this file as the active contract for `/engagement`.
- The active engagement UX contract lives in
  `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`.
- The active engagement API, DB, and queue contracts live in
  `wiki/spec/api/engagement.md`,
  `wiki/spec/database/engagement.md`, and
  `wiki/spec/queue/job-types/engagement.md`.

## What Still Lives Here

This spec is now limited to legacy/compat engagement-control context such as:

- `/engagement_admin` and related `eng:admin:*` paths
- callback-driven manual controls under `eng:set:*`, `eng:join:*`,
  `eng:detect:*`, and `eng:actions:*`
- config-editing mechanics in `bot/config_editing.py`
- older admin/config markups in `bot/ui_engagement.py`
- compat workflow tests that still exercise those surfaces

## Compat Code Anchors

- `bot/main.py` - compatibility exports for legacy imports.
- `bot/callback_handlers.py` - inline callback router.
- `bot/engagement_commands_*.py` - engagement daily, admin, and config command handlers.
- `bot/engagement_*_flow.py` - engagement target, prompt/style, topic, and candidate workflow helpers.
- `bot/runtime*.py` - shared conversation-state, access, parsing, and reply helpers.
- `bot/config_editing.py` - editable field registry, typed parsers, and pending edit state.
- `bot/formatting_engagement.py` - engagement message formatting.
- `bot/ui_engagement.py` - engagement inline markups and callback data builders.
- `bot/api_client.py` - backend engagement API client methods.
- `tests/test_bot_engagement_handlers.py` - engagement bot workflow tests.
- `tests/test_bot_config_editing.py` - config edit parsing and expiry tests.
- `tests/test_bot_ui.py` - callback encoding and markup contract tests.

## Remaining Shards

- [Config Editing](bot-engagement-controls/config-editing.md) - editable config map and conversation state.
- [Controls, Formatting, Tests](bot-engagement-controls/controls-formatting-tests.md) - inline controls, formatting, safety, tests.

Older navigation and slice-contract shards were removed during contract-surface
cleanup because they no longer matched the shipped task-first cockpit contract.
