# Engagement Approval Edit Revised Draft

## Goal

After an operator submits a `Request edit` note from the approval queue, the bot should show the
revised draft as soon as it is available instead of only dropping the operator back into the queue
or home screen.

## Why

- The current flow accepts the free-text correction request but gives weak feedback after submit.
- Operators expect to see the rewritten draft they just asked for when the backend finishes quickly.
- The approval queue already marks replacement candidates with `badge = "Updated draft"`, so the bot
  can reuse the existing queue contract instead of inventing a second review surface.

## Scope

- Update the bot approval-edit submission handler to briefly poll the scoped approvals queue for the
  same engagement after queueing an edit request.
- Render the revised draft card immediately when a replacement draft is already available.
- Fall back to the existing queue/placeholder flow when the rewrite is still pending or no revised
  draft appears within the short wait window.
- Add regression coverage for both the immediate revised-draft path and the fallback path.

## Non-goals

- Changing the backend draft-update contract or adding a new API route.
- Persisting bot-side pending edit state differently.
- Changing approval-card copy outside the revised-draft follow-up behavior.

## Acceptance

- Submitting a draft edit request still clears the pending edit state.
- When the backend already surfaced a replacement draft for the same engagement, the bot sends that
  revised draft card right away.
- When the rewrite is still pending, the bot falls back to the approval queue placeholder/home
  behavior without failing silently.
- Regression tests cover both outcomes.
