# Bot Operator Access

## Goal

Allow the Telegram bot to be shared with an additional human researcher without exposing the control
surface to arbitrary Telegram users.

Telegram premium accounts still send the normal numeric `from_user.id` to bots. The bot can show that
ID to a researcher, and the operator can add it to the configured allowlist.

## Scope

- Add a `/whoami` bot command that returns the sender's Telegram user ID and public username when
  available.
- Add optional `TELEGRAM_ALLOWED_USER_IDS` configuration.
- Preserve existing local/development behavior when the allowlist is unset.
- If the allowlist is set, let unauthorized people see only their own ID plus onboarding guidance.
- Keep authorization in the Telegram bot layer; backend API auth remains unchanged.

## Notes

- The allowlist stores Telegram user IDs, not usernames or phone numbers.
- No person-level scoring or collection behavior changes are involved.
- The collection worker remains untouched.

## Implementation

- Added `TELEGRAM_ALLOWED_USER_IDS` parsing to bot settings.
- Added a public `/whoami` command and an access gate ahead of bot command/callback/document/text
  handlers.
- Added focused tests for config parsing, formatting, and access helper behavior.
