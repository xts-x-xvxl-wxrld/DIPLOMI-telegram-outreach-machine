# Bot Operator Cockpit Spec

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

## Top-Level Navigation

The top-level cockpit should be opened by:

```text
/start
/help
```

Recommended cockpit:

```text
Operator cockpit
  Discovery
  Engagement
  Accounts
  Help
```

Button meanings:

| Button | Destination | Notes |
|---|---|---|
| `Discovery` | Seed-group workflow | Replaces the old `Seed Groups` reply-keyboard label. |
| `Engagement` | Existing `/engagement` cockpit | Opens the engagement daily cockpit. |
| `Accounts` | Account pool health | Uses the same data and masking as `/accounts`. |
| `Help` | Command/help card | Shows concise operator commands and upload hints. |

`Discovery` is preferred over `Seed Groups` because it describes the operator job rather than the
implementation entity. Seed groups remain visible inside the discovery workflow where they matter.

## Interaction Model

The bot should use one primary interaction model:

```text
top-level cockpit
  -> module cockpit or list
  -> item card
  -> state-aware inline actions
```

Slash commands remain valid:

```text
/seeds
/engagement
/engagement_admin
/accounts
/help
```

Rules:

- `/start` should open the cockpit instead of attaching a persistent reply keyboard.
- `/help` may show the cockpit plus command help, but it should not restore the persistent reply
  keyboard.
- Module screens should provide a `Cockpit` or equivalent back button where it helps navigation.
- Existing inline flows for seed groups, communities, jobs, members, engagement candidates, topics,
  settings, targets, prompts, style rules, and audit actions stay intact.
- State-changing actions continue to use explicit buttons or commands with audit-relevant IDs.

## Callback Namespace

Use a compact top-level callback namespace:

```text
op:home
op:discovery
op:accounts
op:help
```

The `eng:*` namespace remains owned by engagement controls.

Suggested mapping:

| Callback | Handler behavior |
|---|---|
| `op:home` | Render the operator cockpit. |
| `op:discovery` | Render the same seed-group overview as `/seeds`. |
| `op:accounts` | Render the same account pool view as `/accounts`. |
| `op:help` | Render help text with cockpit navigation. |

Callback data must stay under Telegram's 64-byte limit.

## Persistent Keyboard Removal

Telegram clients may keep showing an old persistent reply keyboard until the bot explicitly removes
it. The implementation should send a `ReplyKeyboardRemove` once when opening the new cockpit from a
message command if the old keyboard may be present.

Recommended behavior:

1. User sends `/start`.
2. Bot sends a short keyboard-clear message with `ReplyKeyboardRemove`.
3. Bot sends the operator cockpit with inline buttons.

The clear message should be plain and short, for example:

```text
Opening the operator cockpit.
```

The bot should not send `ReplyKeyboardRemove` on inline callback navigation because callback edits or
replies cannot usefully clear a message-level reply keyboard in the same way.

## Command Compatibility

Commands are the durable API for testing, debugging, and direct links. The cockpit must not remove
or weaken them.

Required command behavior after migration:

- `/start` opens the top-level cockpit.
- `/help` opens help and offers the top-level cockpit buttons.
- `/seeds` shows the seed-group overview and seed-group cards.
- `/accounts` shows masked account health.
- `/engagement` opens the existing engagement cockpit.
- `/engagement_admin` opens the existing admin cockpit.

Legacy text messages equal to the old reply-keyboard labels do not need to remain supported after the
old keyboard is removed. If kept temporarily, they should be hidden compatibility aliases rather than
the primary navigation surface.

## Formatting

The cockpit copy should be short and operational.

Recommended home card:

```text
Operator cockpit

Discovery: import and review communities.
Engagement: review replies and participation readiness.
Accounts: check Telegram account health.
Help: commands and upload format.
```

The help card should explain only what an operator needs next:

- CSV upload shape: `group_name,channel`
- direct Telegram handle intake: send `@username` or a public `t.me` link
- key commands for seed groups, engagement, jobs, accounts, and identity

Avoid long marketing or architecture descriptions in the cockpit.

## Discovery Entry

The `Discovery` button should use the existing seed-group overview flow:

```text
op:discovery
  -> list seed groups
  -> seed-group cards
  -> Open, Resolve, Channels, Candidates
```

It must not introduce new backend routes if the existing `/seeds` command can already fetch the
needed data.

Seed cards should continue to expose:

- open seed group
- resolve seed group
- imported channels
- candidate communities

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
- Add top-level callback constants in `bot/ui.py`.
- Extend `parse_callback_data()` to parse the `op:*` namespace.
- Add `format_operator_cockpit()` in `bot/formatting.py`.
- Add `_send_operator_cockpit()`, `_send_seed_groups()`, `_send_accounts()`, and `_send_help()` helpers
  in `bot/main.py`.
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
- Handler test proving `/start` opens the operator cockpit and does not attach the old reply
  keyboard.
- Handler test proving `op:discovery` calls the seed-group overview helper behavior.
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
2. Add reusable send helpers for start/help/seeds/accounts.
3. Switch `/start` and `/help` to the cockpit.
4. Remove persistent reply-keyboard markup from bot responses.
5. Remove old reply-keyboard label handlers, or keep them as hidden aliases for one release.
6. Update tests and docs.

This can ship as one small bot slice because it changes navigation only and reuses existing backend
API calls.

## Open Questions

- Should the first `/start` response always send a keyboard-clear message, or only when a legacy
  keyboard flag is detected in bot state?
- Should the old text labels `Seed Groups`, `Engagement`, `Accounts`, and `Help` remain as hidden
  compatibility aliases for one release?
- Should the top-level `Discovery` card show seed-group counts, or should counts remain inside the
  seed-group overview screen?
