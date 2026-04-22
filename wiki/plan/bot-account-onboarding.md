# Bot Account Onboarding

## Goal

Let operators introduce dedicated Telegram accounts for the `search` and `engagement` pools from the
bot without collecting Telegram login codes, 2FA passwords, or session files in chat.

## Scope

- Add a bot command that accepts an account pool, phone number, optional session name, and optional
  notes.
- Validate that only `search` and `engagement` can be introduced from the bot.
- Return the exact local `scripts/onboard_telegram_account.py` command the operator should run in
  the worker container.
- Keep Telethon login interactive and local to the existing onboarding script.
- Show account pool values in `/accounts` output so operators can confirm search and engagement
  capacity separately.

## Design

`/add_account <search|engagement> <phone> [session_name] [notes...]` is a preparation workflow, not
a remote login workflow. The bot formats a safe Docker Compose command and warns the operator to run
the Telegram login locally.

The backend debug accounts response includes `account_pool` per item and aggregate pool counts. Phone
numbers remain masked before they reach the bot.

## Acceptance

- `/add_account search +10000000000 research-1 "warm spare"` returns an onboarding command with
  `--account-pool search`.
- `/add_account engagement +10000000001 engagement-1` returns an onboarding command with
  `--account-pool engagement`.
- Invalid pools are rejected before formatting a command.
- `/accounts` renders status counts and pool counts with masked phone numbers.
- Fragmentation guardrail and focused bot/onboarding tests pass.
