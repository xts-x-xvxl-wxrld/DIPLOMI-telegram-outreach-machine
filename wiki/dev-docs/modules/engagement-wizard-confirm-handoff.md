# Engagement Wizard Confirm Handoff

## Purpose

Document the task-first wizard confirm seam where the bot turns a successful
`wizard-confirm` response into a visible success note plus a cockpit
destination handoff.

## Owns

- bot-side handling of successful `POST /api/engagements/{id}/wizard-confirm`
  responses
- the split between the short success reply and the inline callback reroute
- use of backend-provided `next_callback` for the confirm success path

## Does Not Own

- backend validation or activation rules for task-first engagement confirm
- engagement detail rendering after the callback handoff lands there
- wizard retry/reset semantics outside the confirm success path

## Read First

- `bot/engagement_wizard_flow.py`
- `bot/callback_handlers.py`
- `bot/engagement_detail_flow.py`
- `backend/services/task_first_engagements.py`
- `tests/test_bot_engagement_wizard.py`

## Entrypoints And Facades

- `_handle_wizard_confirm()` in `bot/engagement_wizard_flow.py`
  - calls the backend confirm endpoint
  - sends the short success reply
  - forwards the inline card to the backend `next_callback`
- `_dispatch_callback()` in `bot/engagement_wizard_flow.py`
  - thin bridge into the callback router stored on `context`
- `_dispatch_callback()` closure in `bot/callback_handlers.py`
  - temporarily swaps `query.data` so callback-only destinations can be
    re-entered without fabricating a new Telegram update

## Main Dependencies

- `wizard_confirm_engagement()` in the bot API client
- `_detail_callback()` output from
  `backend/services/task_first_engagements.py`
- `show_engagement_detail()` in `bot/engagement_detail_flow.py`

## Invariants And Boundaries

- the success note should be a fresh reply, not an edit, so operators can still
  see the "engagement started" confirmation after the wizard card changes
- the inline card should follow the backend `next_callback` when one is present
  instead of hardcoding a local destination
- if no dispatch hook is available, the bot falls back to editing the wizard
  card with the success text rather than failing silently

## Related Tests

- `tests/test_bot_engagement_wizard.py`

## Footguns

- if a test double returns a stale callback shape like `eng:det:{id}` instead
  of the routed `eng:det:open:{id}`, the success path can look green while the
  real callback router would ignore it
- if the success text is sent via edit instead of reply, the user loses the
  confirmation as soon as the cockpit handoff re-renders the inline message
