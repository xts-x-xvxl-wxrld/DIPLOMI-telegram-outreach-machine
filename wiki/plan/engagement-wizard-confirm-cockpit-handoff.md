# Engagement Wizard Confirm Cockpit Handoff

## Goal

Make task-first wizard confirmation keep the success message visible and then
open the backend-directed engagement cockpit destination immediately.

## Scope

- task-first bot wizard confirm success handling
- regression coverage for the success handoff
- wiki contract and developer-doc updates for the confirm seam

## Plan

1. Inspect the wizard confirm handler, backend `wizard-confirm` response, and
   detail-flow callback routing to verify the live handoff contract.
2. Update the bot confirm success path to:
   - send the short success confirmation as a fresh bot reply
   - follow the backend `next_callback` instead of stopping on the review card
3. Add a regression test that proves confirm success now emits the success
   reply and opens the engagement detail surface.
4. Update the relevant spec, developer-doc entry, wiki index, and log so the
   documented task-first flow matches the shipped behavior.

## Acceptance

- successful wizard confirm leaves the celebration message visible in chat
- the inline wizard card transitions into the cockpit destination returned by
  the backend
- the success-path test fails without the handoff and passes with it
