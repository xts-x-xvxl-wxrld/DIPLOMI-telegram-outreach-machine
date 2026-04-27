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

## Callback Namespace And Screen Routing

Use `op:*` for home-entry actions and `eng:*` for engagement surfaces.

Top-level home callbacks:

- `op:home` → `Engagements`
- `op:approve` → `Approve draft`
- `op:issues` → `Top issues`
- `op:engs` → `My engagements`
- `op:sent` → `Sent messages`
- `op:add` → `Add engagement`

These are the only callbacks the home screen should emit.

Surface families:

- `eng:appr` — draft approval queue controller
- `eng:iss` — issue queue controller
- `eng:mine` — engagement list
- `eng:det` — engagement detail
- `eng:sent` — sent-message feed
- `eng:wz` — add/edit wizard

Keep each family to one two-segment callback action and put the verb in
callback parts. This matches the existing callback parser and keeps payloads
short enough for Telegram.

Primary routing:

- `op:approve` and the home draft preview both route to `eng:appr:list:0`
- `op:issues` and the home issue preview both route to `eng:iss:list:0`
- `op:engs` routes to `eng:mine:list:0`
- `op:sent` routes to `eng:sent:list:0`
- `op:add` routes to `eng:wz:start`

Approval callbacks:

- `eng:appr:list:<offset>` — queue controller screen titled `Approve draft`
- `eng:appr:eng:<engagement_id>` — scoped approval queue for one engagement
- `eng:appr:open:<draft_id>` — reopen a specific draft card
- `eng:appr:ok:<draft_id>` — request approve confirmation
- `eng:appr:okc:<draft_id>` — confirm approve
- `eng:appr:no:<draft_id>` — request reject confirmation
- `eng:appr:noc:<draft_id>` — confirm reject
- `eng:appr:edit:<draft_id>` — start draft edit flow

Approval routing rules:

- `eng:appr:list:<offset>` is the queue controller, not a separate archive list
- `eng:appr:eng:<engagement_id>` is the same controller shape, filtered to one
  engagement
- after approve, reject, or completed edit, route back to `eng:appr:list:0`
- if an edit flow exits early, return to `eng:appr:open:<draft_id>`
- when a scoped approval flow launched from engagement detail finishes, return to
  `eng:det:open:<engagement_id>`

Issue callbacks:

- `eng:iss:list:<offset>` — queue controller screen titled `Top issues`
- `eng:iss:eng:<engagement_id>` — scoped issue queue for one engagement
- `eng:iss:open:<issue_id>` — reopen a specific issue card
- `eng:iss:skip:<issue_id>` — mark skipped and advance
- `eng:iss:act:<issue_id>:<action_key>` — launch a concrete fix path

Issue action keys should stay short. Examples:

- `chtopic`
- `crtopic`
- `chacct`
- `resume`
- `retry`
- `apptgt`
- `rsvtgt`
- `fixperm`
- `ratelimit`
- `quiet`
- `swapacct`

Issue routing rules:

- `eng:iss:list:<offset>` is the queue controller for one-by-one issue work
- `eng:iss:eng:<engagement_id>` is the same controller shape, filtered to one
  engagement
- successful fixes return to `eng:iss:list:0`
- early exit from a fix flow returns to `eng:iss:open:<issue_id>`
- skipped issues stay unresolved but the controller still advances
- when a scoped issue flow launched from engagement detail finishes, return to
  `eng:det:open:<engagement_id>`

My-engagement callbacks:

- `eng:mine:list:<offset>` — `My engagements`
- `eng:mine:open:<engagement_id>` — open engagement detail

Engagement-detail callbacks:

- `eng:det:open:<engagement_id>` — detail screen
- `eng:det:resume:<engagement_id>` — resume the primary pending task
- `eng:det:edit:<engagement_id>:topic` — reopen wizard at topic step
- `eng:det:edit:<engagement_id>:account` — reopen wizard at account step
- `eng:det:edit:<engagement_id>:mode` — reopen wizard at sending-mode step

Sent-message callbacks:

- `eng:sent:list:<offset>` — read-only sent-message feed

No row-open callback is needed for `Sent messages` in the first version.

Wizard integration:

- `eng:wz:start`
- `eng:wz:edit:<engagement_id>:topic`
- `eng:wz:edit:<engagement_id>:account`
- `eng:wz:edit:<engagement_id>:mode`

Issue actions such as `Choose topic` and `Choose account` should route through
`eng:wz`, not through separate one-off subflows.

Return-context rule:

- when a draft edit flow or issue fix flow must return to the same item on early
  exit, store that return target in pending state rather than encoding a history
  stack in callback data
- returning home always uses `op:home`

## Data Contract

The task-first cockpit should use explicit read-model payloads instead of
forcing the bot to merge multiple legacy candidate, target, action, and
settings responses on every screen.

Required read models:

- home summary
- approval queue controller
- issue queue controller
- engagement list
- engagement detail
- sent-message feed

Home payload must include:

- `state`
  one of: `first_run`, `approvals`, `issues`, `clear`
- `draft_count`
- `issue_count`
- `active_engagement_count`
- `has_sent_messages`
- `next_draft_preview`
  with draft ID, draft text preview, target label, why text, and `updated` flag
- `latest_issue_preview`
  with issue ID, issue label, engagement ID, created-at timestamp, and optional
  badge label

Approval queue payload must include:

- `queue_count`
- `updating_count`
- `current`
  either the current draft card or `null`
- `placeholders`
  ordered `Updating draft` placeholders when replacements are still pending
- `empty_state`
  one of: `none`, `waiting_for_updates`, `no_drafts`

Current draft card must include:

- draft ID
- engagement ID
- target label
- draft text
- why text
- optional badge label

Issue queue payload must include:

- `queue_count`
- `current`
  either the current issue card or `null`
- `empty_state`
  one of: `none`, `no_issues`

Current issue card must include:

- issue ID
- engagement ID
- issue type
- issue label
- created-at timestamp
- optional badge label
- zero or more fix actions
- the domain IDs needed to resolve those actions safely
  such as candidate ID, target ID, community ID, and assigned account ID when
  applicable

Each fix action must include:

- `action_key`
- label
- destination callback family

Issue mutations should not force the bot to construct low-level permission or
status patches.

Use one semantic issue-action layer:

- `POST /api/engagement/cockpit/issues/{issue_id}/actions/{action_key}`

Allowed mutation results:

- `resolved`
- `next_step`
- `noop`
- `stale`
- `blocked`

The bot should route from the mutation result, not from inferred backend state.

Engagement list payload must include:

- ordered items newest first
- each row's engagement ID
- primary row label
- community label
- sending-mode badge label
- issue-count badge value when non-zero
- pending-task summary when present

Engagement detail payload must include:

- engagement ID
- target label
- topic label
- account label
- sending mode label
- approval count
- issue count
- optional pending task object

Pending task object must include:

- `task_kind`
- label
- count
- resume callback target

Allowed `task_kind` values:

- `approvals`
- `approval_updates`
- `issues`

Pending-task priority on engagement detail:

1. `approvals`
2. `approval_updates`
3. `issues`

Only one primary pending task should surface on engagement detail even when
multiple kinds exist. Lower-priority work remains visible only through counts.

Sent-message payload must include:

- ordered items newest first
- action ID or sent-message ID
- message text
- community label
- absolute send time in the operator's local timezone

The same task-first screen should not have to infer these fields from unrelated
low-level endpoints.

Issue-fix mutation rules:

- direct one-tap fixes should resolve inside the issue-action endpoint
- guided fixes should return `next_step` with the next callback target
- informational actions such as rate-limit detail may return `next_step` without
  mutating anything
- stale issues should return `stale` so the queue can refresh immediately

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

## Issue Generation Contract

The backend must generate cockpit issues from explicit state rules, not from UI
guesswork.

Storage model:

- the backend may materialize issues in a table or synthesize them on read
- behavior must be the same either way

Core rules:

- generate exact issue types, not umbrellas
- allow at most one active issue of a given type per engagement
- when an issue condition changes from false to true, create or surface that
  issue with a fresh `created_at`
- when the condition becomes false, remove the issue immediately from all read
  models
- if the same condition becomes true again later, it is a new issue with a new
  `created_at`
- `Top issues` ordering stays newest first by issue `created_at`

Generation conditions:

- `Topics not chosen`
  emit when a completed engagement has no chosen topic in the engagement read
  model

- `Account not connected`
  emit when the engagement has no usable joined engagement account

- `Sending is paused`
  emit when the engagement is explicitly paused or disabled and would otherwise
  be eligible to run

- `Reply expired`
  emit when a reply opportunity tied to the engagement reaches `expired` while
  still unresolved from the operator's point of view

- `Reply failed`
  emit when a reply opportunity tied to the engagement reaches `failed` and is
  retryable

- `Target not approved`
  emit when the engagement's target exists but is not approved

- `Target not resolved`
  emit when the engagement's target intake has not resolved to a usable
  community

- `Community permissions missing`
  emit when the target/settings permission state does not satisfy what the
  engagement's current sending mode requires

- `Rate limit active`
  emit when account or send limits currently block a real engagement action for
  that engagement

- `Quiet hours active`
  emit when quiet hours currently block a real engagement action for that
  engagement

- `Account restricted`
  emit when the assigned or selected engagement account is banned, restricted,
  or otherwise unusable for the engagement

Do not emit passive non-actionable issues:

- do not emit `Rate limit active` when no real action is currently blocked
- do not emit `Quiet hours active` when no real action is currently blocked
- do not emit duplicate issues that differ only by backend source

Issue payloads should carry the domain IDs needed for safe mutation:

- `engagement_id`
- `candidate_id` when the issue comes from a reply opportunity
- `target_id` when the issue comes from target state
- `community_id` when the issue comes from engagement settings or membership
- `assigned_account_id` when the issue is account-specific

Confirmed issue types and actions:

- `Topics not chosen`
  Actions:
  `Choose topic`
  `Create topic`
  Mutation handling:
  return `next_step` into the wizard topic step

- `Account not connected`
  Action:
  `Choose account`
  Mutation handling:
  return `next_step` into the wizard account step

- `Sending is paused`
  Action:
  `Resume sending`
  Mutation handling:
  resolve directly through a semantic resume-sending mutation

- `Reply expired`
  Action:
  none

- `Reply failed`
  Action:
  `Retry`
  Mutation handling:
  resolve directly through candidate retry

- `Target not approved`
  Action:
  `Approve target`
  Mutation handling:
  resolve directly through target approval

- `Target not resolved`
  Action:
  `Resolve target`
  Mutation handling:
  resolve directly through target resolve-job enqueue

- `Community permissions missing`
  Action:
  `Fix permissions`
  Mutation handling:
  resolve directly through a semantic permission-sync mutation

- `Rate limit active`
  Action:
  `See rate limit`
  Mutation handling:
  return `next_step` into read-only rate-limit detail

- `Quiet hours active`
  Action:
  `Change quiet hours`
  Mutation handling:
  return `next_step` into quiet-hours editing

- `Account restricted`
  Action:
  `Choose another account`
  Mutation handling:
  return `next_step` into the wizard account step

## Issue-Fix Subflow Screens

Not every issue action needs its own screen.

Direct-mutation actions should not open an intermediate subflow screen:

- `Resume sending`
- `Retry`
- `Approve target`
- `Resolve target`
- `Fix permissions`

These should execute their semantic backend mutation immediately and then return
to the issue queue controller.

Wizard-entry issue actions:

- `Choose topic`
- `Create topic`
- `Choose account`
- `Choose another account`

These should enter the existing engagement wizard with stored return context so
early exit returns to the same issue card.

Rate-limit detail screen:

- callback family: `eng:rate`
- title: `Rate limit active`
- body:
  - affected target or engagement
  - blocked account label when available
  - short plain-language reason
  - next retry time in the operator's local timezone when available
- actions:
  - `Back`
  - `<< Engagements`

Rules:

- this is read-only in the first version
- exiting with `Back` returns to the same issue card

Quiet-hours editor screen:

- callback family: `eng:quiet`
- title: `Change quiet hours`
- body:
  - current quiet-hours range
  - short explanation that quiet hours are blocking the engagement right now
- actions:
  - `Edit start`
  - `Edit end`
  - `Turn off quiet hours`
  - `Save`
  - `Cancel`

Rules:

- open this screen prefilled with the engagement's current quiet-hours values
- `Cancel` exits back to the same issue card with no mutation
- successful save returns to the issue queue controller
- `Turn off quiet hours` is equal-weight with editing the range

Scoped return rule:

- any issue-launched subflow must store enough return context to reopen the same
  issue card on early exit
- successful completion should return to the issue queue controller instead
  unless the subflow is explicitly read-only

## Confirmation And Result Copy

Keep confirmations and result messages short.

Confirmation rules:

- require confirmation for `Approve`
- require confirmation for `Reject`
- require confirmation for wizard `Cancel`
- do not require confirmation for direct issue fixes in the first version
- do not require confirmation for quiet-hours `Save`

Confirmation copy:

- `Approve this draft?`
- `Reject this draft?`
- `Cancel setup?`

Confirm/cancel button labels:

- draft approve confirm:
  `Approve` and `Cancel`
- draft reject confirm:
  `Reject` and `Cancel`
- wizard cancel confirm:
  `Confirm cancel` and `Back`

Success copy:

- draft approve:
  `Draft approved`
- draft reject:
  `Draft rejected`
- direct issue fix:
  `Issue resolved`
- resume sending:
  `Sending resumed`
- reply retry:
  `Reply reopened`
- target approve:
  `Target approved`
- target resolve enqueue:
  `Target resolution started`
- permission sync:
  `Permissions fixed`
- quiet-hours save:
  `Quiet hours updated`
- quiet-hours off:
  `Quiet hours turned off`
- wizard confirm:
  `Engagement started`
- wizard cancel:
  `Setup canceled`

Error copy:

- draft approve:
  `Couldn't approve draft`
- draft reject:
  `Couldn't reject draft`
- direct issue fix:
  `Couldn't resolve issue`
- resume sending:
  `Couldn't resume sending`
- reply retry:
  `Couldn't reopen reply`
- target approve:
  `Couldn't approve target`
- target resolve enqueue:
  `Couldn't start target resolution`
- permission sync:
  `Couldn't fix permissions`
- quiet-hours save:
  `Couldn't update quiet hours`
- wizard confirm:
  `Couldn't start engagement`

Result-message rules:

- success and error messages should be one short line
- avoid backend codes in operator-facing copy
- when a queue auto-advances immediately after success, the success line may be
  shown briefly before the next card replaces it
- read-only subflows such as `Rate limit active` do not need a result message

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

Wizard step layout contract:

Step 1 — Target

- title: `Add engagement`
- body:
  - `Step 1 of 5`
  - `Which target?`
  - short helper line: `Paste @handle or t.me/... link`
- behavior:
  - no primary action is shown until the target resolves
  - invalid input re-prompts in place with short error copy

Step 2 — Topic

- title: `Add engagement`
- body:
  - `Step 2 of 5`
  - `Choose a topic or create a new one`
- actions:
  - `Choose topic`
  - `Create topic`
  - `Continue`
- behavior:
  - `Choose topic` and `Create topic` are equal-weight actions
  - the chosen topic shows a selected state
  - `Continue` is enabled only when one topic is selected

Step 3 — Account

- title: `Add engagement`
- body:
  - `Step 3 of 5`
  - `Which account should engage from?`
- actions:
  - one plain list row per available engagement account
  - `Add new account`
- behavior:
  - the account list is plain, not grouped or tabbed
  - choosing an account triggers join work immediately
  - on successful join, auto-advance to the next step

Step 4 — Sending mode

- title: `Add engagement`
- body:
  - `Step 4 of 5`
  - `How should sending work?`
- actions:
  - `Draft`
  - `Auto send`
  - `Continue`
- helper copy:
  - `Draft` — `Review each reply before send`
  - `Auto send` — `Send automatically with limits`
- behavior:
  - `Draft` is preselected by default
  - `Continue` saves the selected mode and moves forward

Step 5 — Final review

- title: `Add engagement`
- body:
  - `Step 5 of 5`
  - target
  - selected topic or topics
  - account
  - sending mode
- actions:
  - `Confirm`
  - `Retry`
  - `Cancel`
- behavior:
  - this screen is read-only
  - `Retry` restarts the wizard from Step 1
  - `Cancel` requires confirmation before discard
  - `Confirm` starts the engagement and opens engagement detail

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

Pending-task rules:

- the detail screen should expose at most one primary pending-task action
- if multiple task kinds exist, use the priority order defined above
- use `Approve draft` for `approvals` and `approval_updates`
- use `Top issues` for `issues`
- scoped pending-task actions launched from detail should return to the same
  detail screen when their queue is exhausted

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

## Display Contract

Keep all secondary screens short and operator-readable.

### Approve Draft

Card shape:

- optional badge line
- draft text
- `Target: <target label>`
- `Why: <why text>`

Rules:

- show the badge `Updated draft` above the draft text when applicable
- do not repeat the draft count inside the card body when the screen already
  shows queue context
- keep `why` to one short line when possible

Queue states:

- if only updating placeholders remain: `Waiting for updated drafts`
- if no drafts remain at all: `No drafts for approval`

### Top Issues

Card shape:

- optional badge line
- issue label
- `Target: <target label>`
- optional short context line when needed
- created-at timestamp in the operator's local timezone

Rules:

- show the badge `Skipped before` above the issue label when applicable
- keep context to one short line; do not dump backend diagnostics into the main
  card
- use the exact issue label as the main card title

Empty state:

- `No issues`

### My Engagements

Row shape:

- line 1: primary label
- line 2: community label
- badges after the text, not inline inside it

Primary label rules:

- use engagement name when it exists
- otherwise use topic name

Badge rules:

- first badge: sending mode
- second badge: issue count, only when non-zero
- issue-count badge text should be `1 issue` or `<n> issues`

Empty state:

- `No engagements`

### Engagement Detail

Body shape:

- `Target: <target label>`
- `Topic: <topic label>`
- `Account: <account label>`
- `Sending mode: <mode label>`
- `Approvals: <count>`
- `Issues: <count>`

Rules:

- keep this screen read-focused; editable fields open the wizard instead of
  exposing inline controls
- if a primary pending-task action exists, it should be the only main action

### Sent Messages

Row shape:

- line 1-2: message text
- next line: community label
- next line: absolute send time in the operator's local timezone

Rules:

- message text may wrap to two lines before truncation
- truncate the message text before truncating community or time
- do not add a separate detail screen in the first version

Empty state:

- `No sent messages`

## Pagination And List Controls

Use simple mobile paging, not free-form filters or dense table controls.

General rules:

- newest-first lists page by offset and limit
- omit pager buttons when the full list fits on one page
- show only valid pager buttons for the current page
- keep list paging separate from the `Back` and `<< Engagements` navigation row

`My engagements` paging:

- default page size: 20
- callback shape:
  `eng:mine:list:<offset>`
- pager labels:
  - `Newer`
  - `Older`
- ordering:
  newest created engagement first
- end-of-list behavior:
  omit `Older` when no more rows exist

`Sent messages` paging:

- default page size: 20
- callback shape:
  `eng:sent:list:<offset>`
- pager labels:
  - `Newer`
  - `Older`
- ordering:
  newest sent message first
- end-of-list behavior:
  omit `Older` when no more rows exist

Queue controllers:

- `Approve draft` and `Top issues` are controller screens, not paged archive
  lists
- they should not show list-pager buttons in the first version

Wizard pickers:

- if topic or account choices exceed one screen, paginate them within the wizard
  using the same `Newer` / `Older` labels
- keep the picker actions and the pager row separate
- keep the selected state visible when moving between pages

## Edge And Empty States

Define empty and blocked states explicitly instead of falling back to generic
error text.

Scoped approval queues launched from engagement detail:

- if drafts remain for that engagement, keep the normal approval card flow
- if only updating placeholders remain for that engagement, stay in the scoped
  queue and show `Waiting for updated drafts`
- if no drafts or updating placeholders remain for that engagement, leave the
  scoped queue and return to that engagement detail screen

Scoped issue queues launched from engagement detail:

- if unresolved issues remain for that engagement, keep the normal issue card
  flow
- if no unresolved issues remain for that engagement, leave the scoped queue
  and return to that engagement detail screen

Global approval and issue queues:

- if a direct action or refresh removes the final remaining draft or issue,
  keep the operator on the same screen and render the empty queue state there
- do not force an automatic jump home when the global queue becomes empty

Stale queue items:

- if a draft or issue disappears before the card opens, refresh the current
  queue controller immediately
- if a direct issue action returns `stale`, refresh the current queue
  controller immediately
- do not show raw stale-object identifiers to the operator

Issue-fix subflows:

- if a subflow opens and the backing issue has already resolved, return to the
  current issue queue controller
- if a subflow exits early by operator choice, return to the same issue card
- if a subflow cannot continue because the editable object no longer exists,
  return to the same issue card with a short one-line error

Rate limit detail:

- if the issue is still active, show the read-only rate-limit screen
- if the issue has cleared before the screen opens, return to the current issue
  queue controller
- if no concrete reset time is available, show the issue label and short status
  without inventing a countdown

Quiet-hours edit:

- if quiet hours are still configured, open the edit screen with current values
- if quiet hours are no longer configured by the time the screen opens, return
  to the current issue queue controller
- if the operator saves without changing anything, treat it as a no-op and
  return to the same issue card

Wizard topic step:

- if no existing topics are available, keep `Create topic` as the only forward
  path
- do not show an empty selectable topic list with dead buttons

Wizard account step:

- show all accounts in the list, even when some are not currently usable
- accounts that cannot be chosen for the current engagement should still be
  visible but marked unavailable
- if no account is currently usable, keep the screen open, show the blocked
  reason in one short line, and do not invent a fallback account

Account-restricted issue flow:

- if at least one other usable account exists, allow normal account reselection
- if no usable replacement account exists, return to the same issue card with a
  short blocked message instead of dropping into an empty picker

Engagement detail:

- if the engagement has no primary pending task, show no main action
- if a pending task existed but clears before `resume` is opened, refresh the
  detail screen and remove the main action

Sent messages and engagement lists:

- when a requested page offset is past the end after underlying data changes,
  return the closest valid page instead of showing a broken empty page
- keep `Newer` omitted on the first page and `Older` omitted on the last page
  even after list shrinkage

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
