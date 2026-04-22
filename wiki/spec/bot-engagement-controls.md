# Bot Engagement Controls Spec

Top-level routing contract for Telegram-native engagement review and admin controls. Detailed
navigation, editing, command, formatting, and test contracts live under
`wiki/spec/bot-engagement-controls/`.

## Purpose

Give operators a compact Telegram bot surface for reviewing reply opportunities, managing approved
engagement targets, editing prompt/style configuration, and inspecting readiness before any public
reply is sent.

## Goals

- Keep daily engagement review fast and low-noise.
- Keep admin controls explicit, permission-gated, and reversible.
- Preserve callback namespaces that route cleanly through `bot/callback_handlers.py`.
- Keep message formatting concise enough for Telegram while exposing readiness blockers.

## Non-Goals

- No autonomous public posting from bot controls.
- No private-message outreach or invite-only community management.
- No hidden admin actions for non-allowlisted operators.

## Interface Summary

- Daily surfaces use `/engagement`, `/engagement_candidates`, candidate detail callbacks, and send
confirmation callbacks.
- Admin surfaces use `/engagement_admin`, target/prompt/topic/style commands, and `eng:admin:*`
callbacks.
- Conversation-state edits are registered in `bot/config_editing.py` and confirmed through
`eng:edit:*` callbacks.
- Formatting and markup are split into `bot/formatting_engagement.py` and `bot/ui_engagement.py`.

## Code Map

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

## Shards

- [Navigation](bot-engagement-controls/navigation.md) - operator modes, navigation, readiness summaries.
- [Config Editing](bot-engagement-controls/config-editing.md) - editable config map and conversation state.
- [Slice Contracts](bot-engagement-controls/slice-contracts.md) - menu gaps, implementation slices, commands.
- [Controls, Formatting, Tests](bot-engagement-controls/controls-formatting-tests.md) - inline controls, formatting, safety, tests.

## Open Questions

- Which oversized engagement test surfaces should be split now that production handler entrypoints are stable?
- Should admin prompt/style tests track the new command and flow modules directly or keep importing through `bot.main`?
