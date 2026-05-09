# Engagement Approval Edit Resume

## Goal

Restore the operator's draft-correction flow when the in-memory pending approval-edit state is lost
or when the operator wants to reopen the edit prompt manually.

## Why

- `Request edit` depends on bot-side pending state keyed by Telegram user ID.
- If that state disappears or the operator navigates away, plain text no longer has enough context to
  resume the correction request.
- Operators need a simple bot command that reopens the same correction prompt without requiring a new
  product surface.

## Scope

- Add a `/resume_edit [draft_id]` Telegram command.
- Reuse the existing approval-edit pending-state flow and prompt formatting.
- Default to the current global approval draft when no `draft_id` is provided.
- Allow an explicit `draft_id` to reopen a non-top draft when it still exists in the approval queue.

## Non-goals

- Adding a new backend API route.
- Persisting approval-edit state in the database.
- Introducing a second correction UX separate from `Request edit`.

## Implementation Notes

- Move the shared approval-edit setup into a reusable helper in
  `bot/engagement_approval_flow.py`.
- Keep callback-driven `Request edit` behavior unchanged by routing it through the same helper.
- Register `/resume_edit` in the bot app command handlers next to `/cancel_edit`.
- Return clear operator-facing errors when the requested draft is no longer in the queue or when no
  draft is available.

## Acceptance

- `/resume_edit` with no args restores the correction prompt for the current approval draft.
- `/resume_edit <draft_id>` restores the correction prompt for that draft when it is still available.
- The restored prompt stores pending approval-edit state so the next free-text message submits the
  correction request normally.
- Missing-draft and empty-queue cases reply with clear bot copy instead of silently doing nothing.
- Regression tests cover default resume, explicit draft resume, and empty-queue handling.
