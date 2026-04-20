# Bot Operator Cockpit Plan

## Goal

Replace the top-level Telegram reply keyboard with the inline operator cockpit described in
`wiki/spec/bot-operator-cockpit.md`.

The change should make the bot entrypoint match the existing engagement cockpit style while keeping
slash commands available for direct access, tests, and audit-friendly links.

## Current Context

Already implemented:

- `/start` and `/help` send `format_start()` with a persistent `main_menu_markup()`.
- `main_menu_markup()` exposes `Seed Groups`, `Engagement`, `Accounts`, and `Help` as reply-keyboard
  buttons.
- Text handlers route those labels to `seeds_command`, `engagement_command`, `accounts_command`, and
  `help_command`.
- `/engagement` already uses an inline cockpit with intention-first controls.
- Seed groups, accounts, jobs, and engagement screens already have inline action buttons.

Problem:

- The top-level entrypoint feels different from the engagement cockpit.
- The persistent keyboard is visually noisy and backend-entity-heavy.
- Command handlers and future callback handlers could drift unless shared helper functions are used.

## Slice 1: Documentation Baseline

Status: completed.

Create:

- `wiki/spec/bot-operator-cockpit.md`
- `wiki/plan/bot-operator-cockpit.md`

Update:

- `wiki/index.md`
- `wiki/spec/bot.md`
- `wiki/log.md`

Acceptance:

- The new spec defines top-level cockpit goals, callback namespace, persistent-keyboard removal,
  command compatibility, formatting, safety rules, tests, and rollout.
- The plan is linked from the wiki index.
- No code changes are made in this slice.

## Slice 2: Cockpit UI And Parser

Status: completed.

Work items:

- Add `op:*` callback constants.
- Add `disc:*` callback constants.
- Add `operator_cockpit_markup()`.
- Add `discovery_cockpit_markup()`.
- Add `reply_keyboard_remove()`.
- Parse `op:home`, `op:discovery`, `op:accounts`, and `op:help`.
- Parse all `disc:*` callbacks.
- Add tests for labels, callback data, and Telegram callback length.

Acceptance:

- Top-level cockpit buttons are inline buttons.
- Existing `eng:*` callbacks still parse as before.

## Slice 3: Shared Send Helpers

Status: completed.

Work items:

- Add `_send_operator_cockpit()`.
- Add `_send_discovery_cockpit()`.
- Split seed-group overview into a reusable `_send_seed_groups()` helper.
- Split account health into a reusable `_send_accounts()` helper.
- Add a reusable `_send_help()` helper.

Acceptance:

- Slash commands and cockpit callbacks render the same screens.
- Seed-group and account flows do not duplicate API calls or formatting logic.

## Slice 4: Remove Persistent Reply Keyboard

Status: completed.

Work items:

- Stop sending `main_menu_markup()` from `/start`, `/help`, `/seeds`, `/accounts`, CSV import, and
  brief-unavailable responses.
- Send `ReplyKeyboardRemove` when opening the new cockpit from message commands.
- Old reply-keyboard label handlers kept as hidden compatibility aliases.

Acceptance:

- `/start` opens the inline cockpit and clears the old keyboard.
- Bot responses no longer attach the old persistent reply keyboard.
- Existing slash commands still work.

## Slice 5: Callback Routing And Tests

Status: completed.

Work items:

- Route `op:home` to the operator cockpit.
- Route `op:discovery` / `disc:home` to the discovery cockpit.
- Route `op:accounts` to account health.
- Route `op:help` to help.
- Route `disc:all`, `disc:attention`, `disc:review`, `disc:watching` to seed groups.
- Route `disc:start`, `disc:activity`, `disc:help` to guidance cards.
- Added `tests/test_bot_handlers.py` with handler tests for all new cockpit callbacks.
- Added cockpit markup and parser tests to `tests/test_bot_ui.py`.
- Regression tests proving engagement cockpit callbacks still parse and route.

Acceptance:

- Every cockpit button has a working destination.
- No cockpit button performs a state-changing action directly.
- Focused bot tests pass.

## Slice 6: Release Documentation

Status: planned.

Update after implementation:

- `wiki/spec/bot.md` if command behavior or UX rules change again.
- `wiki/spec/bot-operator-cockpit.md` if implementation chooses hidden legacy aliases or count
  summaries.
- `wiki/log.md`.

Acceptance:

- Docs match shipped behavior.
- A focused commit contains only related bot cockpit changes.
