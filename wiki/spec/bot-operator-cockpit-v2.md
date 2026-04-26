# Bot Operator Cockpit V2

Radical simplification of the operator cockpit. Replaces the menu-first navigation
with a status-first dashboard that surfaces daily work at one tap.

## Motivation

The current cockpit requires operators to navigate three levels to reach their actual
work: `Home → Engagement → Review replies`. The engagement wizard is buried inside an
Admin sub-screen. Configuration and daily operations are mixed on the same screens.

This spec redesigns the cockpit around a single principle: **the operator should see
what needs doing now and act on it in one tap.**

## Goals

- Surface daily actions (review replies, send queue) directly on the home screen with
  live counts.
- Promote the engagement wizard to a top-level button so adding a community is always
  one tap away.
- Flatten configuration into a single `Manage` screen that replaces the Admin hierarchy.
- Remove the intermediate `Engagement` screen from the daily operator path.
- Keep all existing slash commands, item-level callbacks, and wizard step logic unchanged.

## Non-Goals

- No changes to the wizard flow steps or their contracts.
- No changes to the discovery cockpit (`disc:*`) beyond its back-navigation target.
- No changes to backend API routes or database models.
- No changes to candidate cards, community cards, or any item-level screens.
- No new business logic or automatic sending.

## Home Screen

The home screen is a live dashboard, not a navigation menu.

### Card format

```text
Operator cockpit

⚠ Review: 3 replies
📤 Ready to send: 2
⛔ Needs attention: 1 community

Active topics: 8 · Communities: 12
```

When nothing needs attention:

```text
Operator cockpit

All clear.

Active topics: 8 · Communities: 12
```

The card omits zero counts to reduce noise. A non-zero count on a row is the operator's
signal to act. `Needs attention` covers failed candidates and communities whose last
detect or join job failed.

### Buttons

```text
[💬 Review (3)]  [📤 Send (2)]
[➕ Add community]  [🔍 Discovery]
[⚙ Manage]  [❓ Help]
```

The counts inside `Review` and `Send` buttons are omitted when zero. When positive they
make the action self-explanatory without reading the card.

### Button routing

| Button | Destination | Notes |
|---|---|---|
| `Review` | `eng:candidates needs_review 0` | Skips `eng:home` entirely. |
| `Send` | `eng:candidates approved 0` | Skips `eng:home` entirely. |
| `Add community` | Engagement wizard | Same wizard launched by the old `eng:target_add`. |
| `Discovery` | `disc:home` | Unchanged discovery cockpit. |
| `Manage` | `op:manage` | New flat configuration screen (see below). |
| `Help` | `op:help` | Unchanged help card. |

## Manage Screen

`Manage` replaces the `Engagement → Admin` hierarchy with a single flat screen.

### Card format

```text
Manage

Communities: 12
Topics: 8 · Voice rules: 4
Prompt profiles: 2 · Accounts: 3
```

### Buttons

```text
[🏘 Communities]  [🧩 Topics]
[🗣 Voice rules]  [👤 Accounts]
[🧪 Advanced]
```

| Button | Destination | Notes |
|---|---|---|
| `Communities` | `eng:targets 0` | Same community list as before. |
| `Topics` | `eng:topic_list 0` | Same topic list as before. |
| `Voice rules` | `eng:style all - 0` | Same style rule list as before. |
| `Accounts` | `op:accounts` | Same account pool view as `/accounts`. |
| `Advanced` | `eng:admin_advanced` | Prompt profiles and audit. Unchanged. |

Back navigation on each screen routes to `op:manage`, not `eng:home`.

## Callback Namespace

New top-level callbacks extend the existing `op:*` namespace:

| Callback | Behavior |
|---|---|
| `op:home` | Render the home dashboard. |
| `op:review` | Route to `eng:candidates needs_review 0`. |
| `op:send` | Route to `eng:candidates approved 0`. |
| `op:add` | Launch the engagement wizard. |
| `op:manage` | Render the Manage screen. |
| `op:accounts` | Render account pool health (unchanged). |
| `op:help` | Render help card (unchanged). |
| `op:discovery` | Route to `disc:home` (unchanged). |

The `eng:*` namespace continues to own all item-level actions. The `disc:*` namespace
continues to own all discovery navigation. This spec does not rename or reassign those
callbacks.

## Screens Removed from Operator Path

| Removed screen | Replacement |
|---|---|
| `eng:home` (Engagement today) | `op:home` dashboard |
| `eng:admin` (Engagement admin) | `op:manage` |

`eng:home` and `eng:admin` must remain routable via their existing callbacks and slash
commands (`/engagement`, `/engagement_admin`) for traceability and power-user access.
They are removed from the default navigation path, not deleted.

## Navigation Footer Changes

Back buttons that previously pointed to `eng:home` or `eng:admin` now point to:

- Candidate screens: `Back` → `op:home`.
- Community card / settings screens: `Back` → `op:manage` (Communities).
- Topic, voice rule, prompt profile screens: `Back` → `op:manage`.
- Wizard steps: `Back` → `op:home`.

`Home` buttons on all screens route to `op:home`.

## Command Compatibility

All existing commands remain valid:

| Command | Behavior |
|---|---|
| `/start` | Opens `op:home`. |
| `/help` | Opens `op:help`. |
| `/engagement` | Opens `eng:home` (unchanged, still accessible). |
| `/engagement_admin` | Opens `eng:admin` (unchanged, still accessible). |
| `/engagement_candidates` | Direct candidates list (unchanged). |
| `/engagement_targets` | Direct communities list (unchanged). |
| `/add_engagement_target` | Launches wizard (unchanged). |
| `/seeds` | Discovery seed list (unchanged). |
| `/accounts` | Account pool health (unchanged). |

## Code Map

### New or changed

- `bot/ui_engagement.py` — add `op:review`, `op:send`, `op:add`, `op:manage` callbacks;
  add `operator_home_markup()` and `operator_manage_markup()`.
- `bot/formatting_engagement.py` — add `format_operator_home(data)` and
  `format_operator_manage(data)`. These consume the same counts already returned by the
  engagement home and admin API calls.
- `bot/callback_handlers.py` — route new `op:*` callbacks; update back-navigation
  targets for candidate, community, topic, and style screens.
- `bot/ui_common.py` — add `ACTION_OP_HOME`, `ACTION_OP_REVIEW`, `ACTION_OP_SEND`,
  `ACTION_OP_ADD`, `ACTION_OP_MANAGE` constants.

### Unchanged

- `bot/engagement_wizard_flow.py` — no changes.
- `bot/engagement_commands_wizard.py` — no changes.
- `bot/formatting_engagement_wizard.py` — no changes.
- `bot/ui_discovery.py` — no changes.
- All `disc:*` callbacks — no changes.
- All `eng:*` item-level callbacks — no changes.

## Testing Contract

Minimum tests:

- Unit test: `operator_home_markup()` emits `op:review`, `op:send`, `op:add`,
  `op:discovery`, `op:manage`, `op:help` callbacks.
- Unit test: `operator_manage_markup()` emits callbacks routing to the correct
  existing list screens.
- Unit test: `format_operator_home()` shows non-zero counts and suppresses zero counts.
- Unit test: `format_operator_home()` shows "All clear." when all counts are zero.
- Handler test: `op:review` opens the needs-review candidate list.
- Handler test: `op:send` opens the approved candidate list.
- Handler test: `op:add` launches the engagement wizard.
- Handler test: `op:manage` opens the Manage screen.
- Regression test: `eng:home` and `eng:admin` still respond via command and callback.
- Regression test: existing `eng:*` item-level callbacks are unaffected.

```text
pytest tests/test_bot_ui.py tests/test_bot_handlers.py tests/test_bot_engagement_handlers.py
```

## Rollout

1. Add `ACTION_OP_*` constants and new callback data builders.
2. Implement `operator_home_markup()` and `operator_manage_markup()`.
3. Implement `format_operator_home()` and `format_operator_manage()`.
4. Add `op:*` dispatch in `callback_handlers.py`.
5. Update back-navigation targets in existing markups.
6. Switch `/start` to render `op:home`.
7. Run tests and verify `eng:home` and `eng:admin` remain accessible.

The rollout does not require a backend migration, API changes, or wizard changes.
It ships as a pure navigation layer change.

## Open Questions

- Should `op:home` load live counts on every open, or only refresh on an explicit
  `Refresh` button to avoid latency on every `/start`?
- Should the `Needs attention` count on the home screen include discovery failures
  (failed seed checks, stuck jobs) or only engagement failures in the first slice?
- Should the `eng:home` and `eng:admin` screens be deprecated with a one-release
  notice, or kept indefinitely as power-user paths?
