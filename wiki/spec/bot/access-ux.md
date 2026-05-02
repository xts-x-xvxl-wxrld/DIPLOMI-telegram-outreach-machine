# Bot Access And UX Rules

Operator access, review status, and Telegram UX rules.

## Purpose

The Telegram bot is the MVP operator UI.

It lets the operator import example Telegram communities as seed groups, resolve those examples,
snapshot metadata and visible members for the resolved seed communities, inspect job status, and
start monitoring approved communities.
The operator can also send one public Telegram username or link as plain text; the bot asks the API
to classify it as a channel, group, user, or bot.

The bot talks only to the backend API over HTTP. It never imports backend internals and never talks
directly to Redis, workers, Postgres, web-search providers, Telethon, or OpenAI.

The top-level operator cockpit is specified in `wiki/spec/bot-operator-cockpit.md`. That cockpit
replaces the old persistent reply-keyboard menu with inline navigation while preserving slash
commands as durable shortcuts.
## Operator Access

The bot may be restricted with `TELEGRAM_ALLOWED_USER_IDS`, a comma- or whitespace-separated list of
numeric Telegram user IDs.

There is currently no separate engagement-admin subset. Any Telegram operator who passes the main
bot allowlist may use both daily review controls and engagement setup/configuration surfaces.

The bot may still send `X-Telegram-User-Id` to `GET /api/operator/capabilities` for compatibility,
but the current product decision does not use a distinct admin capability to hide or reject
engagement setup features.

If the allowlist is empty, existing local/development behavior is preserved and any Telegram user who
can reach the bot can use it.

If the allowlist is set, only listed user IDs can use operator commands, reply keyboard actions,
inline callback actions, CSV uploads, or plain-text Telegram entity submission. Unauthorized message
senders receive their own Telegram user ID and instructions to ask the operator to add it. Unauthorized
callback users receive the same information as a Telegram alert.

Prompt-profile edits, style-rule edits, target approval/permission changes, topic mutations, and
advanced community setting changes are all operator-facing controls and should remain available to
any Telegram user who is already authorized to use the bot.

Telegram Premium status does not change this flow; Telegram still includes the same `from_user.id`
for bot messages and callbacks.
## Review Status Decision

MVP review behavior:

- `candidate` - discovered and awaiting review
- `monitoring` - approved and actively scheduled for snapshots or engagement monitoring
- `rejected` - operator rejected
- `dropped` - previously relevant but no longer accessible or intentionally removed
- `approved` - reserved for later workflows where approval and monitoring are separate

The current MVP bot uses approve-as-monitoring to keep the first workflow short.
## UX Rules

- Messages should be concise and operational.
- Plain-text cards should still feel structured: use short headings, section breaks, and action
  blocks so operators can scan them without parse-mode formatting.
- Emojis and glyphs may be used sparingly as visual anchors for status, sections, and high-value
  actions, but they must not replace the underlying text label.
- Default cards should put readiness, summary context, and next safe actions before raw IDs and
  backend-facing detail.
- Button labels should use clear verbs (`Open`, `Approve`, `Queue send`, `Detect now`) and may add a
  leading icon when it improves recognition without making the button wrap awkwardly.
- The top-level bot entry should expose an inline operator cockpit for the main actions.
- Candidate cards must not expose raw message history.
- Candidate cards should explain graph evidence, such as linked discussion, forwarded source,
  Telegram link, or repeated discovery from multiple seeds.
- The bot must never show person-level scores.
- Account phone numbers must be masked by the API before reaching the bot.
- `/add_account` may prepare a local onboarding command for `search` or `engagement` accounts, but
  the bot must not collect Telegram login codes, 2FA passwords, or session files.
- The accounts cockpit should expose add-account buttons for the `search` and `engagement` pools
  and route them to pool-specific `/add_account ...` usage instructions.
- Bot copy should describe communities, not outreach targets.
- Engagement controls must not combine approval and sending unless a later spec explicitly enables
  that workflow.
