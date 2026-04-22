# Bot Discovery Operations Commands

Detailed seed listing, resolution, expansion, job, account, and allowlist helper command contracts.

### `/seeds`

Calls `GET /api/seed-groups` and displays seed group names, IDs, unresolved/resolved/failed seed
counts.

The bot should send an overview message plus compact group cards with inline actions.
### `/resolveseeds <seed_group_id>`

Calls `POST /api/seed-groups/{seed_group_id}/resolve-jobs`.

The bot reports the queued `seed.resolve` job ID. Resolution links imported public Telegram seeds to
candidate `communities` rows and queues initial snapshots for resolved communities.
### `/expandseeds <seed_group_id> [brief_id]`

Optional/future command. The active bare seed-import workflow does not expose expansion in the bot.
When re-enabled, it calls `POST /api/seed-groups/{seed_group_id}/expansion-jobs`.

Expansion can only start from seed rows already resolved to `communities`. The command expands the
seed batch itself, preserving the imported group as the operator-facing context, rather than starting
generic expansion from arbitrary saved community IDs.

`brief_id` is optional future context when expansion returns.
### `/job <job_id>`

Calls `GET /api/jobs/{job_id}` and displays status, timestamps, and a short error if present.

Job messages should include an inline refresh action.
### `/accounts`

Calls `GET /api/debug/accounts` and displays account pool health with masked phone numbers only.
### `/whoami`

Returns the sender's numeric Telegram user ID and public username when available. This command is
available even when `TELEGRAM_ALLOWED_USER_IDS` is configured and the sender is not yet allowed, so a
new human researcher can message the bot and send the ID to the operator.
