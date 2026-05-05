# Task-First Engagement Cockpit

Active Telegram bot contract for the engagement home, wizard, approvals,
issues, detail, and sent feed.

This doc is part of the extracted active contract set:

- `wiki/spec/api/engagement.md`
- `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`
- `wiki/spec/queue/job-types/engagement.md`
- `wiki/spec/database/engagement.md`

## Scope

This is the active operator-facing engagement surface.

It covers:

- home screen and top-level navigation
- task-first add/edit wizard
- approval queue
- issue queue, rate-limit detail, quiet-hours edit
- `My engagements`, detail, and sent feed

Older `eng:topic`, `eng:set`, and `eng:admin` families still exist for
legacy/admin paths, but they are outside this extracted active set. The old
`eng:cand` candidate-review family is retired.

## Home Screen

Title:

- `Engagements`

Always-visible destinations:

- `Approve draft`
- `Top issues`
- `My engagements`
- `Add engagement`
- `Sent messages`

Home has no back button and no `<< Engagements` button.

Button order by state:

- `first_run`
  - `Add engagement`
  - `My engagements`
  - `Top issues`
  - `Approve draft`
  - `Sent messages`
- `approvals`
  - `Approve draft`
  - `Top issues`
  - `My engagements`
  - `Add engagement`
  - `Sent messages`
- `issues`
  - `Top issues`
  - `Add engagement`
  - `My engagements`
  - `Approve draft`
  - `Sent messages`
- `clear`
  - `Add engagement`
  - `My engagements`
  - `Top issues`
  - `Approve draft`
  - `Sent messages`

Count badges:

- `Approve draft (N)` when `draft_count > 0`
- `Top issues (N)` when `issue_count > 0`

Home callbacks:

- `eng:home`
- `op:approve`
- `op:issues`
- `op:engs`
- `op:sent`
- `op:add`

Routing:

- `op:approve` -> approval queue
- `op:issues` -> issue queue
- `op:engs` -> `My engagements`
- `op:sent` -> sent feed
- `op:add` -> wizard start

## Callback Grammar

`parse_callback_data()` treats these as active engagement families:

- `eng:wz`
- `eng:appr`
- `eng:iss`
- `eng:mine`
- `eng:det`
- `eng:sent`
- `eng:rate`
- `eng:quiet`
- `eng:home`
- `op:approve`
- `op:issues`
- `op:engs`
- `op:sent`
- `op:add`

Telegram callback data must stay within 64 characters.

Wizard compacting:

- topic/account picker callbacks use compact 22-character UUIDs
- detail, edit, confirm, retry, and queue callbacks use normal UUID strings

## Wizard Contract

Wizard steps:

1. target entry
2. topic pick/create
3. account pick
4. mode pick
5. review + confirm

Wizard state keys:

- `engagement_id`
- `target_id`
- `community_id`
- `target_ref`
- `topic_id`
- `account_id`
- `mode`
- `join_status`
- `join_message`
- `join_job_id`
- `return_callback`

Core callbacks:

- `eng:wz:start`
- `eng:wz:edit:{engagement_id}:topic`
- `eng:wz:edit:{engagement_id}:account`
- `eng:wz:edit:{engagement_id}:mode`
- `eng:wz:step:{step}:{engagement_id}`
- `eng:wz:tp:{compact_topic_id}:{compact_engagement_id}`
- `eng:wz:tpnew:{compact_engagement_id}`
- `eng:wz:ap:{compact_account_id}:{compact_engagement_id}`
- `eng:wz:lv:draft:{engagement_id}`
- `eng:wz:lv:auto_send:{engagement_id}`
- `eng:wz:confirm:{engagement_id}`
- `eng:wz:retry:{engagement_id}`
- `eng:wz:cancel:{engagement_id | "new"}`
- `eng:wz:cancel_yes:{engagement_id}`

Step navigation:

- step 1: only `Cancel`
- step 2: `Back -> step 1`, `Cancel`
- step 3: `Back -> step 2`, `Cancel`
- step 4: `Back -> step 3`, `Cancel`
- step 5: `Back -> step 4`, explicit edit buttons, explicit cancel

There is no `<< Engagements` button inside the wizard.

Wizard labels and API values:

- button `Draft` -> API `mode = "suggest"`
- button `Auto send` -> API `mode = "auto_limited"`

Stored legacy mode aliases still accepted when reopening state:

- `watching`
- `suggesting`
- `sending`
- `observe`
- `suggest`
- `require_approval`
- `auto_limited`

Wizard write behavior:

- topic selection toggles on/off and writes `PATCH /api/engagements/{id}`
- account selection writes `PUT /api/engagements/{id}/settings`
- mode selection writes `PUT /api/engagements/{id}/settings`
- confirm calls `POST /api/engagements/{id}/wizard-confirm`
- retry calls `POST /api/engagements/{id}/wizard-retry`
- detail delete calls `DELETE /api/engagements/{id}`

Wizard button labels:

- step 2: `Create topic`, optional `Continue ->`
- step 3 empty state: `Add engagement account`, `Accounts`
- step 5: `Confirm`, `Topic`, `Account`, `Mode`, `Cancel`
- retry view: `Retry`
- cancel confirm: `Confirm cancel`, `Back`

## Approval Queue

Callbacks:

- `eng:appr:list:{offset}`
- `eng:appr:eng:{engagement_id}`
- `eng:appr:open:{draft_id}`
- `eng:appr:ok:{draft_id}`
- `eng:appr:okc:{draft_id}`
- `eng:appr:no:{draft_id}`
- `eng:appr:noc:{draft_id}`
- `eng:appr:edit:{draft_id}`

Card actions:

- `Approve`
- `Reject`
- `Request edit`

Flow rules:

- queue screens always keep `<< Engagements`
- scoped queues add `Back -> eng:det:open:{engagement_id}`
- successful approve/reject/edit submission routes back to `eng:appr:list:0`
- placeholder-only queues show `Updating draft`

## Detail And Archive

Detail callbacks:

- `eng:det:open:{engagement_id}`
- `eng:det:resume:{engagement_id}`
- `eng:det:del:{engagement_id}`

Detail actions:

- `Topic`
- `Account`
- `Mode`
- `Archive engagement`

Delete behavior:

- deleting a draft-only engagement removes it and returns to `My engagements`
- deleting an active or historical engagement archives it and returns to
  `My engagements`

## Topic Admin Note

The older admin topic surface now supports `Delete topic` via
`eng:topic:del:{topic_id}`. Unused topics are removed; topics with historical
references are archived.

## Issue Queue

Queue callbacks:

- `eng:iss:list:{offset}`
- `eng:iss:eng:{engagement_id}:{offset}`
- `eng:iss:open:{issue_id}`
- `eng:iss:skip:{issue_id}`
- `eng:iss:act:{issue_id}:{action_key}`

Drill-in callbacks:

- `eng:rate:open:{issue_id}`
- `eng:quiet:open:{engagement_id}:{issue_id}`

Current active issue labels:

- `Topics not chosen`
- `Account not connected`
- `Account connecting`
- `Sending is paused`
- `Reply expired`
- `Reply failed`
- `Target not approved`
- `Target not resolved`
- `Community permissions missing`
- `Rate limit active`
- `Quiet hours active`
- `Account restricted`

Current action keys:

- `chtopic`
- `crtopic`
- `chacct`
- `swapacct`
- `resume`
- `retry`
- `apptgt`
- `rsvtgt`
- `fixperm`
- `ratelimit`
- `quiet`

Callback-family contract from the API:

- wizard-entry fixes carry `callback_family = "eng:wz"`
- semantic issue actions carry `callback_family = "eng:iss"`

Issue UI rules:

- `Skip` is per-user bot state only; it does not resolve the backend issue
- scoped queues use `Back -> eng:det:open:{engagement_id}`
- unscoped queues use `<< Engagements`

## Rate Limit And Quiet Hours

Rate-limit flow:

- button/action opens `eng:rate:open:{issue_id}`
- bot reads `/api/engagement/cockpit/issues/{issue_id}/rate-limit`
- response reopens the originating issue with `next_callback = eng:iss:open:{issue_id}`

Quiet-hours flow:

- button/action opens `eng:quiet:open:{engagement_id}:{issue_id}`
- bot stores pending edit state keyed by Telegram user ID
- operator reply input:
  - `HH:MM-HH:MM`
  - `off`
- bot writes `/api/engagement/cockpit/engagements/{engagement_id}/quiet-hours`
- successful save clears the pending edit state

## My Engagements, Detail, And Sent Feed

List callbacks:

- `eng:mine:list:{offset}`
- `eng:mine:open:{engagement_id}`

Detail callbacks:

- `eng:det:open:{engagement_id}`
- `eng:det:resume:{engagement_id}`

Sent feed callbacks:

- `eng:sent:list:{offset}`

List/detail navigation:

- list footer uses `<< Engagements`
- preview screen uses `View details`
- detail screen uses:
  - pending-task button when the backend returns `pending_task.resume_callback`
  - edit buttons `Topic`, `Account`, `Mode`
  - `Back -> eng:mine:list:0`
  - `<< Engagements`

Pending-task labels:

- `Approve draft`
- `Top issues`

Resume behavior:

- detail fetches fresh backend detail
- if `pending_task.resume_callback` exists, bot redispatches that callback directly
- otherwise it falls back to the detail screen

Sent feed rules:

- pager labels are `Newer` and `Older`
- footer uses `<< Engagements`
- bot never exposes `op:home` from the engagement detail/list/sent surfaces
