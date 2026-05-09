# Engagement Ordinary Approval Notifications

## Goal

Send Telegram alerts for newly created ordinary approval drafts, not only revised drafts produced by
 `Request edit`.

## Why

- The current bot can now follow up when a revised draft rewrite finishes, but brand-new
  `needs_review` drafts still only appear when the operator manually opens the cockpit.
- The repo already documents proactive review notifications as intended behavior, so the active
  task-first bot should surface ordinary approval drafts without requiring manual polling.

## Scope

- Add a bot-side background notifier that starts with the Telegram bot application.
- Poll the task-first approvals queue for explicitly configured operator IDs and detect unseen draft
  IDs.
- Send a Telegram draft-review card when a new ordinary approval draft appears.
- Reuse the same draft-card formatting and approval actions used in the approval queue.
- Prevent duplicate notifications for the same draft during one bot process lifetime, including
  drafts that were already notified by the revised-draft watcher.

## Non-goals

- Building a durable notification delivery service or database-backed dedupe state.
- Implementing the older threshold/idle/snooze notification policy.
- Adding non-Telegram channels such as email or Slack.

## Acceptance

- The bot starts a background notifier only when explicit operator/admin user IDs are configured.
- A newly surfaced ordinary approval draft sends a Telegram message with the draft card and approval
  actions.
- Revised-draft follow-up notifications and ordinary draft notifications share dedupe so the same
  draft is not messaged twice by the same bot process.
- Regression tests cover new-draft detection, dedupe, and startup wiring.
