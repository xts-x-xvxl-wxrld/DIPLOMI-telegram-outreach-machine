# Docker DNS for Telegram Plan

## Goal

Keep local Docker containers from inheriting a DNS resolver that maps Telegram API hosts to
non-Telegram infrastructure.

## Context

The bot container failed during startup because `api.telegram.org` resolved to `109.239.191.125`,
which served a certificate for `essential.hiaware.com`. The same hostname resolved to Telegram
addresses when queried through public DNS.

## Change

Set explicit public DNS resolvers on containers that call Telegram directly:

- `bot`, for Telegram Bot API polling
- `worker`, for Telethon account resolution, expansion, and collection jobs

The API, Redis, and Postgres services keep the default Docker networking behavior.

## Validation

- Recreate the affected containers.
- Confirm `api.telegram.org` resolves to Telegram addresses inside the bot container.
- Confirm an HTTPS request from the bot image no longer fails TLS hostname verification.
- Start the bot container and check that it remains running.
