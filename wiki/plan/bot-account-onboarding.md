# Bot Account Onboarding

## Goal

Let operators introduce dedicated Telegram accounts for the `search` and `engagement` pools from the
bot, while deleting bot messages that contain phone numbers, login codes, or 2FA passwords as soon
as the workflow consumes them.

## Scope

- Add a bot command that accepts an account pool, phone number, optional session name, and optional
  notes, then asks Telegram for a login code through the backend.
- Validate that only `search` and `engagement` can be introduced from the bot.
- Collect the login code and, when Telegram requires it, the account 2FA password through the bot.
- Delete the command, code, and password messages after reading them.
- Create the Telethon session under the shared `SESSIONS_DIR` volume and register the account row.
- Keep `scripts/onboard_telegram_account.py` available as a local fallback.
- Show account pool values in `/accounts` output so operators can confirm search and engagement
  capacity separately.
- Put add-account entrypoints in the accounts cockpit so operators discover onboarding from the
  account-health screen.

## Design

`/add_account <search|engagement> <phone> [session_name] [notes...]` starts an in-bot login
workflow. The API sends the Telegram login code using Telethon, returns a short-lived
`phone_code_hash` to the bot, and the bot stores only the transient onboarding state in memory.
The next text message from that operator is treated as the login code. If Telegram reports that 2FA
is required, the bot asks for the 2FA password and treats the next text message as that password.

The bot attempts to delete all operator messages containing the phone number, login code, or 2FA
password. Deletion is best-effort because Telegram may deny deletion for older messages or chat
permissions. Operators should still use dedicated accounts and avoid sending credentials outside the
allowlisted operator chat.

The backend debug accounts response includes `account_pool` per item and aggregate pool counts. Phone
numbers remain masked before they reach the bot.

The accounts cockpit rendered by `/accounts` and `op:accounts` includes buttons for adding a search
account and an engagement account. Those buttons render pool-specific `/add_account ...` usage
instructions.

## Acceptance

- `/add_account search +10000000000 research-1 "warm spare"` sends a Telegram login code and stores
  transient state for the operator.
- `/add_account engagement +10000000001 engagement-1` sends a login code for the engagement pool.
- The bot deletes command/code/password messages after reading them.
- A valid login code registers the account and reports the pool plus safe session file name.
- A password-required account asks once for the 2FA password and registers after successful sign-in.
- Invalid pools are rejected before formatting a command.
- `/accounts` renders status counts and pool counts with masked phone numbers.
- `/accounts` exposes `Add search` and `Add engagement` buttons that route to pool-specific usage.
- Fragmentation guardrail and focused bot/onboarding tests pass.
