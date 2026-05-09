# Bot Search Temporary Removal

## Goal

Temporarily remove query-driven search from the Telegram bot without disturbing the backend search
pipeline or the seed-first discovery flow.

## Scope

- Stop advertising bot search in the Discovery cockpit copy.
- Keep CSV seed import and direct public Telegram handle intake available.
- Reject legacy `/search*` bot commands and stale inline search callbacks with a clear temporary
  unavailability message.
- Leave backend `/api/search-*` routes, workers, and data model unchanged.

## Implementation

- Reword the Discovery button/copy from `Start search` to example-import guidance.
- Add a bot-side search-access kill switch in `bot/search_handlers.py`.
- Update bot regression tests for the temporary-unavailable path and the renamed Discovery copy.
