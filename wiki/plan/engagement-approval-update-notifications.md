# Engagement Approval Update Notifications

## Goal

Send a follow-up Telegram message when a draft rewrite requested from the approval queue finishes after
the short inline poll window.

## Why

- The current approval-edit flow only shows the revised draft immediately when it arrives within a
  brief synchronous poll.
- When the rewrite takes a little longer, operators fall back to the queue and have to keep checking
  manually.
- A bot-side watcher can close that gap without adding a new backend notification channel or schema
  migration.

## Scope

- Keep the current short inline poll after `Request edit` submission.
- When that poll misses, start a background watcher in the bot approval flow for the same operator,
  chat, engagement, and source draft.
- Poll the scoped approvals queue for a bounded follow-up window and send a Telegram message when an
  `Updated draft` replacement appears.
- Add regression tests for delayed notification delivery and watcher replacement/cancellation safety.

## Non-goals

- Adding a new backend event bus, webhook, or bot API route.
- Persisting watcher state across bot restarts.
- Changing approval queue ordering or draft-card copy beyond the follow-up notification message.

## Acceptance

- Immediate revised-draft behavior still works when the replacement appears during the short inline
  poll.
- When the replacement appears later but within the watcher window, the bot sends a new Telegram
  message with the revised draft card and approval actions.
- Starting a new approval-update watcher for the same operator replaces the older pending watcher
  cleanly.
- Existing fallback behavior still returns the operator to the queue/home when no immediate
  replacement is ready.
