# Bot Search Temporary Removal

## Purpose

Capture the current bot-side seam for temporarily disabling query-driven search while keeping the
Discovery cockpit usable for CSV import, direct public handle intake, and review/watch workflows.

## Verified Files

- `bot/search_handlers.py`
- `bot/callback_handlers.py`
- `bot/ui_discovery.py`
- `bot/formatting_discovery.py`
- `tests/test_bot_search_handlers.py`
- `tests/test_bot_handlers.py`
- `tests/test_bot_formatting.py`
- `tests/test_bot_ui.py`

## Current Behavior

- `bot/search_handlers.py` owns the temporary kill switch through
  `SEARCH_BOT_ACCESS_ENABLED = False`.
- All public `/search...` command handlers short-circuit before calling the API client and reply
  with a shared unavailability message that redirects operators to CSV upload or direct public
  handle intake.
- `_handle_search_callback()` also short-circuits known search callback actions, which blocks stale
  inline search cards already present in Telegram chat history.
- The Discovery cockpit still uses `ACTION_DISC_START`, but `bot/ui_discovery.py` now labels it as
  `Add examples` and `bot/callback_handlers.py` renders import guidance instead of a search hub.

## Developer Notes

- This is a bot-only change. Backend search routes, jobs, and workers remain live for later
  re-enable or non-bot callers.
- Re-enabling bot search later is primarily a matter of flipping the guard in
  `bot/search_handlers.py` and restoring Discovery copy that should again advertise the feature.
