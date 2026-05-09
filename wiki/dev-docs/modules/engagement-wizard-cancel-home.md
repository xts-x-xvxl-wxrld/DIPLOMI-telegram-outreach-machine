# Engagement Wizard Cancel Home

## Purpose

Document the task-first wizard cancel-confirm seam where the bot discards the
pending wizard state and immediately restores the shared `Engagements` home
surface.

## Owns

- bot-side handling of `eng:wz:cancel_yes:{engagement_id}`
- bot-side handling of `eng:wz:cancel_no:{engagement_id}`
- the handoff from wizard cancel confirmation back to the shared cockpit home
- reuse of the standard home formatter and markup after cancellation

## Does Not Own

- the cancel-confirm prompt itself
- engagement deletion or cleanup of draft backend rows
- engagement home state computation on the backend

## Read First

- `bot/engagement_wizard_flow.py`
- `bot/engagement_wizard_cancel_flow.py`
- `bot/callback_handlers.py`
- `bot/formatting_engagement_home.py`
- `bot/ui_engagement_home.py`
- `tests/test_bot_engagement_wizard.py`

## Entrypoints And Facades

- `_handle_wizard_callback()` in `bot/engagement_wizard_flow.py`
  - routes `cancel_yes` and `cancel_no` after the confirm prompt
- `show_wizard_cancel_home()` in `bot/engagement_wizard_cancel_flow.py`
  - fetches cockpit-home payload after the pending wizard state is cleared
  - edits the inline wizard card into the standard `Engagements` home screen
- `handle_wizard_cancel_back()` in `bot/engagement_wizard_cancel_flow.py`
  - reopens the current wizard step instead of hardcoding a return to review
- `show_wizard_cancel_prompt()` in `bot/engagement_wizard_cancel_flow.py`
  - owns the confirm-cancel prompt copy and inline markup
- `_send_cockpit_home()` in `bot/callback_handlers.py`
  - remains the shared callback-router entrypoint for explicit `eng:home`
    navigation outside the cancel-confirm seam

## Invariants And Boundaries

- `cancel_yes` must clear the pending wizard state before the home render so a
  new `Add engagement` starts from Step 1
- `cancel_no` should resume the current wizard step from pending state rather
  than assuming the operator came from Step 5
- the post-cancel screen should use `format_cockpit_home()` plus
  `cockpit_home_markup()` instead of duplicating home copy or buttons locally
- cancel keeps the operator in the engagement cockpit instead of leaving a
  text-only dead end

## Related Tests

- `tests/test_bot_engagement_wizard.py`

## Footguns

- routing `cancel_yes` through a synthetic callback dispatch adds an avoidable
  dependency on callback-router internals; render the home card directly here
- if the wizard state is not cleared before rendering home, the next wizard
  launch can accidentally reopen with stale pending data
- hardcoding `Back` to Step 5 breaks Step 1-4 cancels because the confirm
  prompt can appear from any wizard step
