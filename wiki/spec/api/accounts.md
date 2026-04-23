# Account Onboarding API

## Responsibility

Expose bot-facing Telegram account onboarding endpoints behind bearer-token auth.

## Endpoints

- `POST /api/telegram-accounts/onboarding/start`
  - Request: `account_pool`, `phone`, optional `session_name`, optional `notes`, optional
    `requested_by`.
  - Behavior: validates the account pool and session name, creates the session path under
    `SESSIONS_DIR`, asks Telegram to send a login code, and returns `phone_code_hash` for the
    transient bot workflow.
- `POST /api/telegram-accounts/onboarding/complete`
  - Request: start fields plus `phone_code_hash`, `code`, optional `password`.
  - Behavior: signs in with the login code, asks for password only when Telegram requires 2FA,
    validates authorization, and upserts `telegram_accounts`.

## Invariants

- Only `search` and `engagement` pools may be onboarded.
- Session names must stay inside `SESSIONS_DIR`.
- The API does not persist login codes, 2FA passwords, or `phone_code_hash`.
- The bot owns deletion of sensitive chat messages; API responses must not echo login codes or
  passwords.
