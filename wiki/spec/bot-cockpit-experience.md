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

### Problem

The operator must remember to open the bot to find out if reviews are waiting. There
is no push signal. Reviews silently pile up and expire without the operator knowing.

### Behavior

The bot proactively sends a notification message to the operator when the pending
review count crosses a threshold and the operator has not been active recently.

### Trigger conditions

A notification is sent when **all** of the following are true:

1. Pending review count ≥ `notify_review_threshold` (default: 3).
2. At least `notify_min_interval_minutes` have passed since the last notification
   (default: 60 minutes). This prevents repeat alerts.
3. At least `notify_idle_minutes` have passed since the operator last interacted with
   the bot (default: 30 minutes). Notifications are suppressed while the operator is
   actively using the cockpit.

### Notification card

```text
⚠ 5 replies are waiting for your review.

Oldest is 2 hours old.
```

### Notification buttons

```text
[💬 Review now]  [🔕 Snooze 2h]
```

`Review now` routes to `op:review` (the needs-review candidate list).

`Snooze 2h` suppresses notifications for 2 hours without the operator having to open
the full cockpit. Snooze state is per-operator and stored in bot state.

### Delivery mechanism

Notifications are delivered by the existing cron/scheduler infrastructure, not by
inline bot logic. A scheduled task runs at a configurable interval (default: every
15 minutes) and evaluates trigger conditions for each active operator.

The task calls the engagement API for pending counts, checks idle time from session
state, checks last-notification time from bot state, and sends via the bot's
`send_message` if conditions are met.

### Configuration keys

Stored in `config/config.json` under `engagement_notifications`:

```json
{
  "engagement_notifications": {
    "enabled": true,
    "notify_review_threshold": 3,
    "notify_min_interval_minutes": 60,
    "notify_idle_minutes": 30,
    "snooze_duration_minutes": 120
  }
}
```

All keys are optional with the defaults above. Set `enabled: false` to disable
proactive notifications without removing the config block.

### Non-goals

- No per-community notifications.
- No notifications for approved-to-send queue (operator controls send timing).
- No email or external channel delivery — Telegram only.
- No notification for discovery queue items in the first slice.

---

## 5. Attention And Navigation

The detailed contracts for the unified `Needs attention` count and the navigation
footer rules now live in
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
