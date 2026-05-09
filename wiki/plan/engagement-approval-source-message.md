## Goal

Show the triggering source message on the task-first draft approval screen so operators can review
the exact chat context before approving or rejecting a reply.

## Scope

- task-first cockpit approval payload
- approval-card Telegram formatting
- focused API and bot regression tests
- matching bot/API spec and developer-doc updates

## Implementation Notes

1. Extend the cockpit approval item contract with source-message fields taken from the underlying
   `engagement_candidates` row.
2. Render a `Source message` section on the approval card and keep missing-field fallbacks safe for
   stale/non-current draft views.
3. Update the approval-related docs and tests so the payload shape and bot copy remain synchronized.

## Acceptance

- approval cards show the triggering message excerpt when it is available
- approvals API returns the source-message fields needed by the bot
- existing stale/placeholder approval flows keep working without new required fields
