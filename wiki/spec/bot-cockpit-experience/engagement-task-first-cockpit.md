# Task-First Engagement Cockpit

Resolved UX contract for the engagement cockpit.

Supersedes `wiki/spec/bot-operator-cockpit-v2.md` for engagement-cockpit
direction.

Companion to:

- `wiki/spec/bot/engagement-add-wizard.md`
- `wiki/spec/bot-engagement-controls/navigation.md`
- `wiki/spec/bot-cockpit-experience.md`

## Product Direction

The engagement cockpit is a working surface for one non-technical Telegram
operator.

It should stay short, exact, and action-first.

The operator priority order is:

1. approve drafts
2. resolve issues
3. add new engagements

The cockpit should not expose backend entities, low-level permission flags, or
menu-tree thinking in the main operator path.

## Core Rules

- The home screen title is `Engagements`.
- The home screen has no back or home navigation.
- Home actions use one primary button per row in strict priority order.
- The main operator path should use exact issue labels, not broad umbrella
  labels, whenever a clearer split is possible.
- The wizard is the default path for adding and editing engagements.

## Home Visibility Rules

- `Approve draft` appears only when drafts are waiting.
- `Top issues` appears only when issues exist.
- `Sent messages` appears only when at least one sent message exists.
- `My engagements` appears whenever any finished engagement exists.
- `Add engagement` appears in every non-first-run state.

## Home States

### First Run

Use when there are zero finished engagements.

Message:

```text
Engagements

Add your first engagement
Tap add engagement...
```

Actions:

```text
[Add engagement]
```

Rules:

- Do not show `Continue setup`.
- Canceled or incomplete setup should not surface here.

### Approval-Focused State

Use when drafts are waiting.

Message:

```text
Engagements

2 drafts need approval
1 issue needs attention: Topics not chosen
```

The second line appears only if issues exist.

Action order:

1. `Approve draft`
2. `Top issues`
3. `My engagements`
4. `Add engagement`

Rules:

- Hide `Sent messages` in this state.

### Issues Present, No Approvals

Message:

```text
Engagements

1 issue needs attention
```

Rules:

- Do not append the active-engagement count here.

Action order:

1. `Top issues`
2. `Add engagement`
3. `My engagements`
4. `Sent messages`

### No Pending Work

Message:

```text
Engagements

No pending work
3 active engagements
```

Action order:

1. `Add engagement`
2. `My engagements`
3. `Top issues`
4. `Sent messages`

Only show actions that pass the visibility rules above.

## Naming

Top-level labels:

- `Engagements`
- `Approve draft`
- `Top issues`
- `My engagements`
- `Add engagement`
- `Sent messages`

Secondary screen titles should match their entry action labels exactly.

Examples:

- `Approve draft`
- `Top issues`
- `My engagements`
- `Add engagement`
- `Sent messages`

## Navigation

Home:

- no back button
- no home button

Outside the wizard:

- `Back` goes one step back
- `<< Engagements` returns home immediately

Inside the wizard:

- show only step-by-step `Back`
- do not show `<< Engagements`
- leaving the wizard is handled by the wizard flow itself

Using `<< Engagements` outside the wizard should leave immediately without an
extra warning.

## Draft Approval Flow

Entry:

- tapping the home draft preview opens the review flow
- the home preview shows draft text only
- preview length should be about three Telegram lines

Review model:

- one draft at a time
- after `Approve`, `Reject`, or completed `Edit`, auto-advance to the next item
- when the queue is finished, return home

Draft card content:

- draft text
- target
- why the draft was suggested

Draft actions:

- `Approve`
- `Reject`
- `Edit`

Rules:

- `Approve` requires confirmation
- `Reject` requires confirmation
- exiting an edit flow early returns to the same draft card
- completing an edit flow auto-advances immediately

Edited-draft behavior:

- edited drafts stay in the queue
- when the updated replacement draft is ready, it reappears at the top
- while waiting, show a passive placeholder row labeled `Updating draft`
- multiple placeholders sit at the top and preserve original queue order
- if only updating placeholders remain, keep the operator in queue and show
  `Waiting for updated drafts`
- if no drafts are waiting at all, show `No drafts for approval`
- updated drafts should appear automatically without manual refresh
- updated drafts should carry the badge `Updated draft`

## Issue Flow

Entry:

- tapping the home issue preview opens the first issue directly
- the home preview shows the latest issue
- `Top issues` is ordered newest first

Issue model:

- one issue at a time
- resolving an issue auto-advances to the next issue
- resolved issues disappear immediately everywhere, including home preview and
  engagement issue-count badges
- `Skip` is always available
- skipped issues stay unresolved
- skipped issues stay visible until resolved
- inside the issue flow, `Skip` still moves forward to the next issue
- if the same issue happens again later for the same engagement, it comes back
  as a brand-new issue with a fresh date

Issue screens should not rely on one generic resolve path.
They should surface concrete actions that can resolve the issue.

If multiple valid fixes exist:

- show all valid actions
- give them equal weight

If a fix action opens another flow and the operator exits early:

- return to the same issue card

If the issue is shown again after skip:

- show the badge `Skipped before`

Treat this badge only as local state for the current single-operator model.

## Confirmed Issue Taxonomy

The first version of `Top issues` should ship only with confirmed issue types.
Do not include broader plausible-but-unconfirmed operational issues yet.

Do not use broad umbrella issue labels when a more exact split is available.

Confirmed issue types and actions:

- `Topics not chosen`
  Actions:
  `Choose topic`
  `Create topic`

- `Account not connected`
  Action:
  `Choose account`

- `Sending is paused`
  Action:
  `Resume sending`

- `Reply expired`
  Action:
  none

- `Reply failed`
  Action:
  `Retry`

- `Target not approved`
  Action:
  `Approve target`

- `Target not resolved`
  Action:
  `Resolve target`

- `Community permissions missing`
  Action:
  `Fix permissions`

- `Rate limit active`
  Action:
  `See rate limit`

- `Quiet hours active`
  Action:
  `Change quiet hours`

- `Account restricted`
  Action:
  `Choose another account`

## Add Engagement Wizard

Entry rules:

- `Add engagement` always launches the wizard immediately
- if the operator previously abandoned a setup flow, starting again should start
  fresh immediately
- do not restore unfinished setup

Wizard order:

1. target
2. choose existing topic or create new one
3. account selection
4. sending mode
5. final review

Topic choice:

- existing topic and new topic are equal options

Account selection:

- plain list

Sending modes:

- `Draft`
- `Auto send`

Default:

- `Draft`

Final review:

- read-only
- actions:
  `Confirm`
  `Cancel`
  `Retry`

Behavior:

- `Retry` restarts the wizard from the beginning
- `Cancel` requires confirmation before discard

Editing existing engagements:

- tapping topic, account, or sending mode in engagement detail reopens the full
  wizard
- existing values should be prefilled
- the wizard should jump to the tapped step
- the operator can still go backward to earlier steps

## My Engagements

List behavior:

- simple list
- no filters for now
- order by most recently created first
- show completed engagements only
- incomplete engagements remain hidden until finished

Each row should show:

- engagement name plus community, or topic name plus community if topics are
  named
- sending mode badge first
- issue-count badge second, only when non-zero

Rules:

- do not show draft counts in the row
- do not add more row badges for now

Tapping a row opens engagement detail.

## Engagement Detail

Show:

- target
- topic
- account
- sending mode
- approval status as count with short label
- issue status as count with short label

If the engagement has pending work:

- the main action should resume that pending task

If there is no pending task:

- no main action is needed yet

Editable fields:

- topic
- account
- sending mode

## Sent Messages

Behavior:

- top-level but low priority
- hidden when approvals exist
- global feed
- newest first
- read-only
- no filters for now

Each row should show:

- message text
- community
- absolute send time

Use the same `Back` plus `<< Engagements` navigation pattern.

## Badge Convention

Prefer compact badge labels over extra inline explanatory copy for surfaced
state.

Confirmed badges:

- `Updated draft`
- `Skipped before`
- sending mode badge in `My engagements`
- issue-count badge in `My engagements`

## Non-Goals

- No exposure of raw engagement permission flags on the main cockpit.
- No `Continue setup` action on home.
- No requirement that the operator understands backend entities before acting.
- No broad recent-activity history surface in the main cockpit.
- No generic issue umbrella when a more exact issue split is available.
