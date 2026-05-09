# Bot Cockpit Experience

Behavioral and structural companion notes for the task-first cockpit
direction. Primary UX source of truth:
`wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`.

This shard is no longer allowed to define competing home-screen, navigation, or
wizard-topology rules. If any text here conflicts with the task-first cockpit
spec, the task-first cockpit spec wins.

Companion to
`wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md` and
`wiki/spec/bot-cockpit-simplification.md`.

Covers only secondary behavior that does not replace the main task-first
cockpit contract.

The task-first engagement cockpit blueprint now lives in
`wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`.

---

## 1. First-Run Empty State
Defined by
`wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`.

Do not use the older `Operator cockpit`, discovery-first, or partial-setup home
contracts that previously lived in this shard.

---

## 2. Proactive Review Notifications

### Behavior

The active bot may proactively send a Telegram draft-review card when an unseen
ordinary approval draft appears in the task-first approvals queue.

### Trigger conditions

A notification is eligible when all of the following are true:

1. The draft is currently visible in the task-first approvals queue.
2. The draft ID has not already been surfaced to that operator during the
   current bot-process lifetime.
3. The operator is an explicit configured bot user ID from the bot settings.

### Notification card

The notification reuses the same draft card content and approval actions as the
interactive approvals queue.

### Delivery mechanism

Notifications are delivered by a bot-side background polling task that starts
with the Telegram application. The task pages through the approvals queue and
sends a Telegram message for unseen draft IDs.

The current slice uses in-memory per-operator dedupe only. A bot restart can
resend still-pending drafts because there is no durable notification
acknowledgement yet.

### Non-goals

- No threshold-, idle-, or snooze-based policy yet.
- No per-community notifications.
- No notifications for approved-to-send queue.
- No email or external channel delivery.
- No notification for discovery queue items in this slice.

---

## 5. Attention And Navigation

The detailed contracts for the unified `Needs attention` count and the
navigation footer rules now live in
`wiki/spec/bot-cockpit-experience/attention-and-navigation.md`.

That shard is a companion only. Where it conflicts with the task-first cockpit
spec on home labels, top-level routing, or footer behavior, the task-first
cockpit spec wins.

That shard should cover only:

- issue-list routing and related technical notes that do not redefine the home
  screen
- navigation details that stay consistent with `Back` plus `<< Engagements`
- technical implementation notes for subordinate screens
- the related API and test contracts
