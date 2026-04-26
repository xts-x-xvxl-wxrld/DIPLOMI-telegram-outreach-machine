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

## 5. "Needs Attention" — Unified Definition

### Problem

Both the v2 home dashboard and the discovery cockpit have a "Needs attention" concept,
defined independently with no shared contract. The home dashboard's count may be
inconsistent with what the discovery cockpit surfaces. The operator sees two different
"attention" signals with no clear relationship.

### Decision: unified count on home, breakdown in each section

The home dashboard `Needs attention` count is the **union** of engagement and discovery
failures. It answers: "is there anything broken that requires my input right now?"

Each section (Engagement → candidate list with `failed` status, Discovery → attention
screen) shows its own breakdown when the operator drills in.

### What counts as "Needs attention"

#### Engagement (always included)

| Condition | Example |
|---|---|
| Candidates with `failed` status | Draft generation failed, send failed |
| Communities whose last detect job failed | Worker error, account issue |
| Communities whose last join job failed | FloodWait unresolved, ban |

#### Discovery (included in home count from the start)

| Condition | Example |
|---|---|
| Searches with failed example checks | Private channel, not found |
| Searches with no usable examples | All examples failed |
| Collection jobs that failed for watched communities | Snapshot error |

### What does not count

- Candidates in `needs_review` status — these are normal work, shown in the Review count.
- Candidates in `approved` status — shown in the Send count.
- Candidates in `sent`, `rejected`, or `expired` status — terminal states, no action needed.
- Discovery candidates pending review — surfaced in Discovery, not as Needs attention.

### Home card format

```text
Operator cockpit

⚠ Review: 3 replies
📤 Ready to send: 2
⛔ Needs attention: 4     ← engagement (2) + discovery (2)
```

The count is a single number. The breakdown is visible only when the operator taps
into the relevant section. Discovery failures appear in `disc:attention`.
Engagement failures appear in the candidate list filtered to `failed` status.

### "Needs attention" tap routing

Tapping `Needs attention` on the home dashboard routes to whichever section has
the higher count. If engagement failures dominate, route to `eng:candidates failed 0`.
If discovery failures dominate, route to `disc:attention`. If equal, prefer engagement.

A `Home` back button is always present on the routed screen so the operator can
return without navigating back through the section.

### API contract

The home dashboard API call must return:

```json
{
  "needs_review": 3,
  "approved": 2,
  "attention_engagement": 2,
  "attention_discovery": 2
}
```

The bot sums `attention_engagement` and `attention_discovery` for the display count
and stores both to determine tap routing.

---

## 6. Navigation Footer Contract

### Problem

Back and Home buttons are added ad hoc to each screen. Different screens use different
back targets, some screens have no navigation footer at all, and new screens drift
from whatever implicit convention existed before.

### Navigation levels

Every screen belongs to one of four levels:

| Level | Examples |
|---|---|
| 0 — Home | `op:home` |
| 1 — Section home | `op:manage`, `disc:home`, `op:help`, `op:accounts` |
| 2 — List | Community list, topic list, candidate list, style rule list |
| 3 — Item card | Community card, candidate card, topic card, prompt card |
| Modal | Wizard steps, confirmation dialogs, config edit prompts |

### Footer rules

| Screen level | Back button | Home button |
|---|---|---|
| 0 — Home | None | None |
| 1 — Section home | None | `Home` → `op:home` |
| 2 — List | `Back` → parent level 1 | `Home` → `op:home` |
| 3 — Item card | `Back` → parent level 2 | `Home` → `op:home` |
| Modal | `Back` → previous modal step or entry point | None |

Rules:

- **Level 0** has no footer. It is the home.
- **Level 1** has `Home` only. Back is omitted because there is no meaningful parent
  below the home screen — pressing Home does the same thing.
- **Level 2** has both `Back` and `Home`. Back goes to the section that owns the list,
  not to the previous message in Telegram history.
- **Level 3** has both `Back` and `Home`. Back goes to the list that owns the item.
- **Modal** screens have `Back` only. `Home` is omitted from modals because abandoning
  a multi-step flow by jumping to home leaves partial state. The operator should use
  `/cancel_edit` or step back through the flow.

### Stable back targets

`Back` routes to a **stable, named parent**, not to a per-message history stack.
The target is determined by the screen's place in the hierarchy, not by how the
operator navigated there.

| Screen | Back target |
|---|---|
| Community list (`eng:targets`) | `op:manage` |
| Topic list (`eng:topic_list`) | `op:manage` |
| Style rule list (`eng:style`) | `op:manage` |
| Candidate list (`eng:candidates`) | `op:home` |
| Community card (`eng:target_open`) | `eng:targets 0` |
| Candidate card (`eng:candidate_open`) | `eng:candidates <status> 0` |
| Settings card (`eng:settings_open`) | Community card for that community |
| Topic card | `eng:topic_list 0` |
| Style rule card | `eng:style all - 0` |
| Prompt profile card | `eng:prompts 0` |
| Discovery list screens | `disc:home` |
| Discovery item cards | Parent discovery list |

### Wizard exception

Wizard steps are modals. Each step's `Back` button returns to the previous step, not
to the screen that launched the wizard. The wizard is exited via `/cancel_edit` or by
completing it.

On completion, the wizard lands the operator on the community settings card for the
newly configured community (level 3), with a standard `Back` → community list and
`Home` → `op:home` footer.

### Implementation notes

- `_with_navigation` in `bot/ui_common.py` accepts `back_action`, `back_parts`, and
  `home_action` parameters. Audit every call site to verify it matches the level rules
  above.
- Add a `home_action` default of `ACTION_OP_HOME` to `_with_navigation`. Screens that
  are level 0 or level 1 pass `include_home=False` explicitly.
- Modal screens pass `include_home=False`.
- The `Home` button label is always `🏠 Home` for consistency. `Back` is always `← Back`.

### Testing contract

- Unit test: every `*_markup()` function in `bot/ui_engagement.py` and `bot/ui_discovery.py`
  that represents a level-2 or level-3 screen includes both `Back` and `Home` buttons.
- Unit test: every level-1 markup includes `Home` and omits `Back`.
- Unit test: `operator_home_markup()` includes neither `Back` nor `Home`.
- Unit test: wizard step markups include `Back` and omit `Home`.
