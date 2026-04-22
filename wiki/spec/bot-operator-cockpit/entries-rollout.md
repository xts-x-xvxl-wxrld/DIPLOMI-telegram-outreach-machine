# Bot Operator Cockpit Entries And Rollout

Engagement, accounts, help, implementation, safety, testing, rollout, and open question contracts.

## Purpose

This spec defines the top-level Telegram bot operator cockpit.

The current bot mixes two navigation styles:

- a persistent reply keyboard with `Seed Groups`, `Engagement`, `Accounts`, and `Help`
- inline cockpit-style controls inside engagement screens

The target design removes the persistent reply keyboard and makes `/start` open a Telegram-native
inline cockpit. The cockpit becomes the operator entrypoint for discovery, engagement, account
health, and help while existing slash commands remain available for traceability, testing, and power
users.

This spec extends:

- `wiki/spec/bot.md`
- `wiki/spec/bot-engagement-controls.md`
- `wiki/plan/tg-bot-ux-control-surface.md`

It does not change backend ownership. The bot remains a control surface over backend API routes and
must not import backend internals or talk directly to Redis, Postgres, Telethon, OpenAI, or workers.
## Goals

- Replace the ugly top-level reply keyboard with an inline operator cockpit.
- Make the bot entrypoint match the engagement cockpit interaction style.
- Organize top-level navigation around operator intentions instead of backend entity names.
- Keep commands such as `/seeds`, `/engagement`, `/accounts`, and `/help` working.
- Avoid duplicate handler logic by routing cockpit buttons through the same helpers as commands.
- Clear the old persistent keyboard for operators who already have it open in Telegram.
- Keep all state-changing actions behind existing explicit command or inline callback paths.
## Non-Goals

- No frontend web work.
- No new backend business logic.
- No changes to discovery, collection, analysis, engagement, or account-manager safety rules.
- No automatic engagement sending.
- No person-level scoring, ranking, or outreach lists.
- No generic database editing surface in the bot.
- No removal of slash commands.
## Engagement Entry

The `Engagement` button should call the existing engagement cockpit behavior:

```text
op home
  -> eng:home
```

The engagement cockpit remains defined by `wiki/spec/bot-engagement-controls.md` and should keep its
intention-first entries:

- Today
- Review replies
- Approved to send
- Communities
- Topics
- Recent actions
- Admin

Approval and sending must remain separate.
## Accounts Entry

The `Accounts` button should render the same account health view as `/accounts`.

Rules:

- Phone numbers must remain masked by the API before reaching the bot.
- The bot should not show secrets, session paths, or raw local account files.
- Account pool labels may be shown when available because pool separation is operator-relevant.
## Help Entry

The `Help` button should render the same command help as `/help`, but with inline cockpit navigation.

Help must include:

- how to upload seed CSVs
- how to submit one public Telegram handle or link
- how to inspect jobs
- how to open engagement controls
- how to run `/whoami` for allowlist onboarding
## Implementation Notes

Recommended code shape:

- Add `operator_cockpit_markup()` in `bot/ui.py`.
- Add `discovery_cockpit_markup()` in `bot/ui.py`.
- Add top-level callback constants in `bot/ui.py`.
- Add discovery callback constants in `bot/ui.py`.
- Extend `parse_callback_data()` to parse the `op:*` and `disc:*` namespaces.
- Add `format_operator_cockpit()` in `bot/formatting.py`.
- Add `format_discovery_cockpit()` and discovery help/readiness formatting helpers in
  `bot/formatting.py`.
- Add `_send_operator_cockpit()`, `_send_seed_groups()`, `_send_accounts()`, and `_send_help()` helpers
  in `bot/main.py`.
- Add `_send_discovery_cockpit()` and route `op:discovery` to it.
- Make command handlers and callback handlers call the same helpers.
- Remove `main_menu_markup()` usage from command responses.
- Remove or deprecate reply-keyboard label `MessageHandler` registrations.

The helper split matters because button callbacks and slash commands should not drift into two
separate implementations of the same screen.
## Safety Rules

- The cockpit must not bypass allowlisted bot operator access.
- Unauthorized callback users receive the same access-denied alert behavior as other callbacks.
- No cockpit button may perform a state-changing action directly.
- State-changing actions must remain on item cards or explicit commands with IDs.
- Engagement send controls must appear only for approved candidates.
- Collection, discovery, expansion, and analysis flows must not perform outbound engagement actions.
- The bot must never show person-level scores.
## Testing Contract

Minimum tests:

- UI test for `operator_cockpit_markup()` labels and callback data.
- Callback parser test for `op:home`, `op:discovery`, `op:accounts`, and `op:help`.
- UI test for `discovery_cockpit_markup()` labels and `disc:*` callback data.
- Callback parser test for `disc:home`, `disc:start`, `disc:attention`, `disc:review`,
  `disc:watching`, `disc:activity`, `disc:help`, and `disc:all`.
- Handler test proving `/start` opens the operator cockpit and does not attach the old reply
  keyboard.
- Handler test proving `op:discovery` opens the Discovery cockpit.
- Handler test proving Discovery cockpit destinations use existing seed/search helpers where
  available.
- Handler test proving `op:accounts` renders account health with the existing masking contract.
- Handler test proving `op:help` renders help and cockpit navigation.
- Regression test proving old engagement cockpit callbacks still parse and route.

Recommended focused command:

```text
pytest tests/test_bot_ui.py tests/test_bot_handlers.py tests/test_bot_engagement_handlers.py
```

If test files are reorganized, run the equivalent focused bot UI, formatting, and handler tests.
## Rollout

Recommended rollout:

1. Add the operator cockpit UI and callback parser.
2. Add the Discovery cockpit UI and `disc:*` callback parser.
3. Add reusable send helpers for start/help/seeds/accounts/discovery.
4. Switch `/start` and `/help` to the cockpit.
5. Route `op:discovery` to the Discovery cockpit.
6. Remove persistent reply-keyboard markup from bot responses.
7. Remove old reply-keyboard label handlers, or keep them as hidden aliases for one release.
8. Update tests and docs.

This can ship as one small bot slice because it changes navigation only and reuses existing backend
API calls.
## Open Questions

- Should the first `/start` response always send a keyboard-clear message, or only when a legacy
  keyboard flag is detected in bot state?
- Should the old text labels `Seed Groups`, `Engagement`, `Accounts`, and `Help` remain as hidden
  compatibility aliases for one release?
- Should the Discovery cockpit show live counts in the first implementation, or should counts wait
  until cheap read models exist?
- Should `Start search` become a multi-step conversation for naming a search and adding examples, or
  stay as guidance plus CSV/direct-link intake for the first slice?
- Should `Needs attention` include collection failures from already watched communities in the first
  slice, or should it initially focus only on search/example setup issues?
