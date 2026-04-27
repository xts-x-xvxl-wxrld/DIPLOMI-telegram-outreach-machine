# Bot Cockpit Experience

Behavioral and structural contracts that complete the v2 cockpit redesign.
Companion to `wiki/spec/bot-operator-cockpit-v2.md` and
`wiki/spec/bot-cockpit-simplification.md`.

Covers: first-run empty state, proactive review notifications, unified "Needs
attention" definition, and navigation footer consistency rules.

---

## 1. First-Run Empty State

### Problem

A new operator opens the bot for the first time. There are no communities, no topics,
no accounts. The v2 home dashboard shows "All clear" — accurate but useless. The
operator has no signal that they need to set something up before the bot can do
anything.

### Detection

The home screen is in first-run state when all of the following are true:

- Zero approved engagement communities.
- Zero active engagement topics.
- Zero ENGAGEMENT-pool accounts.

Any one of those conditions being satisfied means setup has started and the standard
dashboard applies (even if it shows low counts).

### First-run card

```text
Operator cockpit

Welcome. Nothing is set up yet.

To start engaging, add your first community.
The wizard will walk you through topics, account, and engagement level.
```

### First-run buttons

```text
[➕ Add first community]
[🔍 Discovery]  [❓ Help]
```

`Add first community` launches the engagement wizard identically to `op:add` on the
standard home screen. No separate flow is needed.

`Discovery` and `Help` remain available in case the operator wants to import seed
communities first or read the help card before setting up engagement.

### Partial setup state

If setup has started but is incomplete — for example, one topic exists but no
communities — the standard dashboard applies. The "All clear" empty message is
replaced by a partial-state hint:

```text
Operator cockpit

No communities set up yet.

[➕ Add community]  [🔍 Discovery]
[⚙ Manage]  [❓ Help]
```

The counts row is omitted when all counts are zero. The `Add community` button is
promoted to the top row to keep the next action visible.

### Implementation notes

- `format_operator_home` in `bot/formatting_engagement.py` receives the count
  payload. Add a helper `_is_first_run(data)` that checks for zero on
  `approved_community_count`, `active_topic_count`, and `account_count`.
- `operator_home_markup` in `bot/ui_engagement.py` accepts a `first_run: bool`
  parameter and renders the appropriate button set.
- The API call that populates the home dashboard must include `approved_community_count`
  and `account_count` alongside the existing reply counts.

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

That shard covers:

- the combined engagement + discovery attention count and tap routing
- footer level rules (`Home`, `Back`, modal exceptions)
- stable back targets and wizard navigation behavior
- the related API and test contracts
