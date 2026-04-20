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
- Child screens should include a navigation footer with `Back` and `Home` inline buttons whenever a
  logical parent exists. `Back` routes to the stable parent screen for that card or list; it is not a
  per-message browser history stack. `Home` routes to the top-level operator cockpit.
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
| `op:discovery` | Render the Discovery cockpit. |
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

The `Discovery` button should open a Discovery cockpit rather than dropping the operator directly
into backend seed-group lists.

Recommended Discovery cockpit:

```text
Discovery
  Start search
  Needs attention
  Review communities
  Watching
  Recent activity
  Help
```

This cockpit reframes the core search workflow around what the operator is trying to do:

| Button | Operator meaning | Backend concepts behind it |
|---|---|---|
| `Start search` | Add example communities for a new or existing search. | seed groups, seed channels, CSV import, direct Telegram entity intake |
| `Needs attention` | Show searches or communities that need operator attention before they can move forward. | unresolved seeds, failed seed resolution, failed collection, queued/stuck jobs |
| `Review communities` | Decide which suggested communities should be watched. | candidate communities, seed-group candidate lists, review decisions |
| `Watching` | Inspect communities already approved for monitoring. | communities with `monitoring` status, collection runs, latest snapshots |
| `Recent activity` | Inspect recent background work, job outcomes, and operational events. | seed resolution, collection, expansion/future jobs |
| `Help` | Show discovery-specific input guidance. | CSV shape, public link rules, direct commands |

The first implementation should reuse existing backend routes where possible. It should not
introduce new API routes merely to rename the operator surface. If a screen needs a filtered view
that existing routes cannot provide, add a read-only API route before adding bot-only filtering
logic.

### Discovery Vocabulary

The UI should translate backend nouns into operator-facing language:

| Backend term | Operator label |
|---|---|
| `seed_group` | Search |
| `seed_channel` | Example community |
| `resolve seeds` | Check examples |
| `candidate` | Suggested community |
| `approve` | Watch |
| `reject` | Skip |
| `collection` | Collect details |
| `job` | Recent job or background work |

Backend IDs remain available on detail cards for traceability, but cards should lead with the
operator label and readiness summary.

### Discovery Home Card

Recommended copy:

```text
Discovery

Next: Review 24 suggested communities.

Needs attention: 3 searches
Review communities: 24
Watching: 11 communities
Recent activity: 2 jobs need attention
```

The home card should be action-biased. The `Next:` line should name the most useful next step based
on current state, for example:

```text
Next: Start a search with example communities.
Next: Check 3 searches that need attention.
Next: Review 24 suggested communities.
Next: Inspect 2 failed jobs.
```

The exact counts may be omitted in the first slice if the API does not expose them cheaply, but the
card should still preserve the `Next:` line and the six-entry cockpit shape.

### Discovery Callback Namespace

Use a compact discovery-specific namespace under the top-level operator cockpit:

```text
disc:home
disc:start
disc:attention
disc:review
disc:watching
disc:activity
disc:help
disc:all
disc:search:<search_id>
disc:examples:<search_id>:<offset>
disc:check:<search_id>
disc:candidates:<search_id>:<offset>
disc:watch:<community_id>
disc:skip:<community_id>
```

The `op:discovery` callback should route to `disc:home` behavior. The existing seed-group callback
namespace may remain in place for item-level actions during the transition, but new discovery
navigation should use `disc:*`.

### Start Search

`Start search` should be a small search hub rather than only an upload hint.

Recommended hub:

```text
Start search
  New search
  Add examples to existing search
  All searches
  CSV format
```

Button meanings:

| Button | Operator meaning | Backend concepts behind it |
|---|---|---|
| `New search` | Start a discovery set from fresh example communities. | create/import seed group |
| `Add examples to existing search` | Add more example communities to a known search. | append seed channels to seed group |
| `All searches` | Browse every search, including searches with no current alert or review queue. | list seed groups |
| `CSV format` | Show import format and public-link rules. | seed CSV documentation |

The first implementation may keep `New search` and `Add examples to existing search` as guidance
around the current CSV/direct-intake flow rather than a full multi-step conversation.

`Start search` should explain these input paths:

- upload a CSV with `group_name,channel`
- send one public `@username` or `t.me` link for direct classification
- use an existing community as an example when that workflow is added

The `All searches` path is important even when it is not a top-level cockpit button. It prevents
searches from disappearing when they are not currently in `Needs attention`, `Review communities`,
or `Watching`.

### Needs Attention

`Needs attention` should show searches or communities that need operator attention before they can
move forward:

- searches with unresolved example communities
- searches with failed example checks
- searches with setup jobs that failed or are stuck
- searches with no usable examples
- watched communities whose collection jobs failed
- any discovery job that needs inspection or retry

Cards should explain the next safe action before raw counts:

```text
Search: Hungarian SaaS founders

Readiness: Needs attention
Examples checked: 21 of 24
Needs attention: 3 failed examples

Next: Check examples
```

### Review Communities

`Review communities` should show suggested communities waiting for a human decision.

Candidate cards should answer:

- what the community is
- why the system found it
- which search it belongs to
- what happens if the operator chooses the primary action

Recommended card shape:

```text
Open SaaS Hungary

Readiness: Needs review
Why found: Mentioned by 3 example communities
Signals: linked discussion, forwarded source
Members: 4,820
Search: Hungarian SaaS founders

Suggested next step: Watch this community
Community ID: <id>
```

Recommended buttons:

- `Watch`
- `Skip`
- `Show why`
- `Community profile`

`Watch` maps to the existing review-approve behavior that moves a community to monitoring and
queues collection. `Skip` maps to the existing reject behavior. Approval and rejection commands may
remain named `/approve` and `/reject`, but the normal button-led path should use `Watch` and `Skip`.

### Watching

`Watching` should show communities already approved for monitoring.

Cards should emphasize operational state:

- latest collection status
- latest snapshot summary when available
- latest analysis summary when available
- whether engagement settings exist when engagement is enabled

Recommended buttons:

- `Community profile`
- `Collect details`
- `Members`
- `Engagement`

### Recent Activity

`Recent activity` should collect background work and outcomes into one operational view:

- seed/example checks
- collection jobs
- expansion jobs when re-enabled
- failed jobs that need inspection

The view should provide refresh controls and short failure messages. It should avoid exposing noisy
worker internals until the operator opens a job detail card.

The operator-facing label should be `Recent activity`; individual rows may still be job cards when
the underlying object is a job.

### Discovery Help

`Discovery Help` should be shorter and more focused than global help:

- CSV upload columns: `group_name`, `channel`
- optional CSV columns: `title`, `notes`
- public Telegram references only
- private invite links are rejected
- direct handle intake accepts `@username` and public `t.me` links
- no people search and no person-level scores

### Discovery Readiness Summaries

Search cards should use one of these readiness labels before raw fields:

- `Needs examples`
- `Ready to check examples`
- `Checking examples`
- `Ready to review`
- `Review in progress`
- `Watching communities`
- `Needs attention: examples failed`
- `Needs attention: collection failed`
- `Paused`

Example-community cards should use:

- `Not checked yet`
- `Checking`
- `Confirmed public community`
- `Already known`
- `Failed: private or unavailable`
- `Failed: not a community`

Suggested-community cards should use:

- `Needs review`
- `Strong match`
- `Already watching`
- `Skipped`
- `Needs details`
- `Collecting details`
- `Ready to inspect`

Readiness summaries are display explanations of backend state. They must not replace backend
validation or review state.

### Seed-Group Compatibility

Seed cards should continue to expose the existing operations while they are renamed in the UI:

- open seed group
- check examples
- example communities
- suggested communities

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
