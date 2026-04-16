# Frontend Spec

## Purpose

The web frontend is a later operator interface for reviewing seed groups, candidates, watchlists,
collection runs, and community summaries.

It is not part of the first MVP slice. The Telegram bot is the initial operator UI.

## MVP Deferral

Frontend implementation waits until the seed-first workflow has real candidate data and the bot
review loop exposes the most important operator needs.

## Future Views

Expected views:

- seed group list and detail
- seed channel resolution status
- seed-group candidate review with graph evidence summaries
- watchlists and monitoring state
- community detail
- collection run history
- analysis summaries
- account health/debug status
- optional audience brief list and detail, if the brief layer returns

## API Boundary

The frontend should consume the backend API only.

It must not connect directly to workers, Redis, Postgres, web-search providers, Telethon, or OpenAI.

## Safety Rules

- Do not expose raw messages by default.
- Do not show person-level scores.
- Do not show Telegram account phone numbers unless a future admin-only endpoint explicitly allows it.
- Keep the product centered on community discovery, monitoring, and review.
