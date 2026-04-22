# Bot Operator Cockpit Navigation

Top-level navigation, interaction, callback namespace, keyboard removal, command compatibility, and formatting contracts.

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
