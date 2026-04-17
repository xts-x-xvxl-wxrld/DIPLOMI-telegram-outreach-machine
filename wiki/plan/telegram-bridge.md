# Telegram Bridge

## Goal

Let the operator, Codex sessions, and VPS helper bots exchange short operational messages through the
existing Telegram bot without giving bots Telegram account sessions or weakening the seed-review bot
controls.

## Scope

- Add optional bridge settings to the bot process.
- Let allowlisted Telegram users send ordinary text to a bridge inbox JSONL file.
- Keep public Telegram usernames and `t.me` links on the existing entity-intake path.
- Add a `/bridge` command that reports the current chat ID and bridge inbox path.
- Add a local script that sends a named bot/Codex message to the configured Telegram chat through the
  Telegram Bot API.
- Keep the bot token and chat ID in environment variables, never in source.

## Design

- The bridge is disabled unless `TELEGRAM_BRIDGE_ENABLED` is truthy.
- Inbound messages are appended as one JSON object per line to `TELEGRAM_BRIDGE_INBOX_PATH`.
- Each inbound record includes a generated message ID, timestamp, chat ID, user ID, username, source,
  and text.
- The send script reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BRIDGE_CHAT_ID`, then calls
  `sendMessage`.
- Docker mounts `./data` into the bot container so the inbox can be inspected from the VPS checkout.

## Safety

- Existing `TELEGRAM_ALLOWED_USER_IDS` checks still apply before a message enters the bridge.
- `/whoami` remains available for onboarding.
- The bot token must be rotated if exposed and should only be placed in `.env` or VPS secrets.
- The bridge does not add collection-worker behavior, person-level scoring, or outreach targeting.
