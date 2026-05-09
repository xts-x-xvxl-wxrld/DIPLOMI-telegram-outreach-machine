# Engagement Wizard Cancel Home

## Goal

Make the task-first engagement wizard's confirmed cancel action return the
operator to the `Engagements` home screen instead of leaving a terminal
"Setup cancelled" message in chat.

## Scope

- bot-side `eng:wz:cancel_yes` handling in the task-first wizard flow
- regression coverage for the post-cancel home render
- spec/doc updates for the cancel handoff

## Acceptance

- confirming cancel clears the pending wizard edit state
- the wizard card re-renders as the shared `Engagements` home surface
- the home screen keeps the normal cockpit actions (`Approve draft`,
  `Top issues`, `My engagements`, `Add engagement`, `Sent messages`)
- the cancel flow no longer leaves a dead-end text-only message
