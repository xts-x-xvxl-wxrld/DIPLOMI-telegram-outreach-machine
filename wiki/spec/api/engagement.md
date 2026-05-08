# API Engagement

Active engagement API contract extracted from code and tests.

This doc is part of the extracted active contract set:

- `wiki/spec/api/engagement.md`
- `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`
- `wiki/spec/queue/job-types/engagement.md`
- `wiki/spec/database/engagement.md`

## Scope

This doc covers only the active engagement API surfaces:

- task-first engagement create, patch, settings, confirm, retry, delete
- cockpit home, approvals, issues, engagement list/detail, sent feed
- cockpit approval and issue mutations
- cockpit rate-limit and quiet-hours drill-ins

Legacy community-scoped settings, targets/topics admin CRUD, prompt/style admin,
and older candidate/action routes still exist in the repo, but they are outside
this extracted active contract set.

All routes here are mounted under `/api` and require the bot token dependency.

## Task-First Write Path

### `POST /api/engagements`

Request:

- `target_id: uuid`
- `created_by: string(1..200)`

Success:

- status `201`
- response `result: "created" | "existing" | "reopened"`
- `engagement` fields:
  - `id`, `target_id`, `community_id`
  - `topic_id`
  - `status`
  - `name`
  - `created_by`, `created_at`, `updated_at`

Rules:

- target must exist
- target must already be `resolved` or `approved`
- target must already point at a `community_id`
- one engagement row exists per `target_id`
- if the row already exists, return it with `result = "existing"`
- if the existing row is `archived`, reopen it as a fresh draft and return it
  with `result = "reopened"`
- newly created rows start as:
  - `topic_id = null`
  - `status = "draft"`
  - `name = null`

Errors:

- `404 {code:"target_not_found"}`
- `409 {code:"target_not_resolved"}`

### `PATCH /api/engagements/{engagement_id}`

Partial request:

- `topic_id?: uuid | null`
- `name?: string | null` (trimmed; blank becomes `null`)

Response:

- `result: "updated" | "blocked" | "stale"`
- `engagement?: TaskFirstEngagementOut`
- `message?: string`
- `code?: string`

Rules:

- archived engagements are blocked with `code = "engagement_archived"`
- missing engagements return `result = "stale"` and `code = "engagement_stale"`
- `topic_id` may be cleared only while the engagement is still `draft`
- non-null `topic_id` must reference an active `engagement_topics` row

Codes:

- `engagement_stale`
- `engagement_archived`
- `topic_edit_blocked`
- `topic_missing`

### `PUT /api/engagements/{engagement_id}/settings`

Partial request:

- `assigned_account_id?: uuid | null`
- `mode?: "disabled" | "observe" | "suggest" | "require_approval" | "auto_limited"`
- `max_posts_per_day?: int(0..300)`
- `min_minutes_between_posts?: int(>=1)`
- `quiet_hours_start?: HH:MM | null`
- `quiet_hours_end?: HH:MM | null`

Active write-path rules:

- the task-first path only accepts `mode = "suggest"` or `mode = "auto_limited"`
- settings rows are created lazily if missing; creation defaults are:
  - `mode = "disabled"`
  - `allow_join = false`
  - `allow_post = false`
  - `reply_only = true`
  - `require_approval = true`
  - `max_posts_per_day = 300`
  - `min_minutes_between_posts = 1`
- if `assigned_account_id` is provided and non-null, the account must:
  - exist
  - not be `banned`
  - belong to the `engagement` account pool
- if `max_posts_per_day` is written, it must stay between `0` and `300`
- if `min_minutes_between_posts` is written, it must stay at or above `1`
- quiet hours are all-or-nothing on write:
  - both `quiet_hours_start` and `quiet_hours_end`
  - or neither
- when `mode` is written:
  - `allow_join = true`
  - `allow_post = (mode == "auto_limited")`

Response:

- `result: "updated" | "blocked" | "stale"`
- `settings?: {engagement_id, assigned_account_id, mode, max_posts_per_day, min_minutes_between_posts, quiet_hours_start, quiet_hours_end}`
- `message?: string`
- `code?: string`

Codes:

- `engagement_stale`
- `engagement_archived`
- `account_missing`
- `account_unusable`
- `invalid_max_posts_per_day`
- `invalid_min_minutes_between_posts`
- `invalid_quiet_hours`
- `sending_mode_unsupported`

### `POST /api/engagements/{engagement_id}/wizard-confirm`

Request:

- `requested_by?: string(1..200)`; route falls back to `"operator"`

Response:

- `result: "confirmed" | "validation_failed" | "blocked" | "stale"`
- `message: string`
- `next_callback: string`
- `engagement_id?: uuid`
- `engagement_status?: string`
- `target_status?: string`
- `field?: string`
- `code?: string`

Validation rules:

- target must still resolve to a community
- target status must not be `pending`, `failed`, `rejected`, or `archived`
- engagement must have an active topic
- settings must exist with:
  - `assigned_account_id`
  - `mode in {"suggest","auto_limited"}`

State changes on success:

- promote the community to `approved` if it is not already `approved` or `monitoring`
- set target:
  - `status = "approved"`
  - `allow_join = true`
  - `allow_detect = true`
  - `allow_post = (mode == "auto_limited")`
  - `approved_at` if missing
  - `approved_by` if missing
- set settings:
  - `allow_join = true`
  - `allow_post = (mode == "auto_limited")`
- transition engagement `draft -> active`

Queue side effects:

- if the selected account is not already joined to the community:
  - enqueue `community.join`
- otherwise:
  - enqueue manual `collection.run` with `reason = "manual"`

Returned callbacks:

- success: `eng:det:open:{engagement_id}`
- missing/invalid topic: `eng:wz:edit:{engagement_id}:topic`
- missing account: `eng:wz:edit:{engagement_id}:account`
- invalid mode: `eng:wz:edit:{engagement_id}:mode`
- target problems: `eng:wz:edit:{engagement_id}:target`
- stale missing engagement: `op:add`

Blocking codes:

- `engagement_archived`
- `target_not_resolved`
- `target_not_approved`
- `join_enqueue_failed`
- `collection_enqueue_failed`

Validation fields:

- `topic`
- `account`
- `mode`

### `POST /api/engagements/{engagement_id}/wizard-retry`

Response:

- `result: "reset" | "blocked" | "stale"`
- `message: string`
- `next_callback: string`
- `engagement_id?: uuid`
- `code?: string`

Rules:

- only `draft` engagements can reset
- reset clears:
  - `engagement.topic_id -> null`
  - `settings.assigned_account_id -> null`
  - `settings.mode -> "disabled"`
  - `settings.allow_join -> false`
  - `settings.allow_post -> false`

Returned callbacks:

- success: `eng:wz:start`
- stale: `op:add`
- blocked active or archived engagement: `eng:det:open:{engagement_id}`

Codes:

- `engagement_archived`
- `engagement_active`

### `DELETE /api/engagements/{engagement_id}`

Response:

- `result: "deleted" | "archived" | "stale"`
- `message: string`
- `next_callback: string`
- `engagement_id?: uuid`
- `code?: string`

Rules:

- draft engagements with no runtime candidate history are physically deleted
- active, paused, and historical engagements are archived instead
- delete/archive disables task-first send/join settings
- archive clears target allow flags and archives the target

Codes:

- `engagement_stale`

Compat note:

- topic deletion remains on the older admin topic surface as
  `DELETE /api/engagement/topics/{topic_id}`

## Cockpit Read Path

### `GET /api/engagement/cockpit/home`

Response:

- `state: "first_run" | "approvals" | "issues" | "clear"`
- `draft_count`
- `issue_count`
- `active_engagement_count`
- `has_sent_messages`
- `next_draft_preview?`
  - `draft_id`, `engagement_id`, `text_preview`, `target_label`, `why`, `updated`
- `latest_issue_preview?`
  - `issue_id`, `engagement_id`, `issue_type`, `issue_label`, `badge`, `created_at`

State selection:

- `first_run` when there are no visible `active` or `paused` engagements
- `approvals` when approvals exist
- `issues` when there are issues but no approvals
- `clear` otherwise

### `GET /api/engagement/cockpit/approvals`
### `GET /api/engagement/cockpit/engagements/{engagement_id}/approvals`

Response:

- `queue_count`
- `updating_count`
- `offset`
- `empty_state: "none" | "waiting_for_updates" | "no_drafts"`
- `placeholders[]: {slot, label}`
- `current?: {draft_id, engagement_id, target_label, engagement_label, community_label, text, why, badge}`

Rules:

- only `needs_review` candidates tied to visible `active` or `paused` engagements appear
- hidden source drafts stay out of the queue while an update request exists
- completed replacement drafts surface with `badge = "Updated draft"`
- pending draft-update requests surface as `Updating draft` placeholders
- `engagement_label` is the operator-facing primary engagement label: `engagement.name`, then topic
  name, then community title, then engagement UUID as last resort
- `community_label` is the operator-facing community label: `@username`, then community title, then
  community UUID as last resort

### `GET /api/engagement/cockpit/issues`
### `GET /api/engagement/cockpit/engagements/{engagement_id}/issues`

Response:

- `queue_count`
- `offset`
- `empty_state: "none" | "no_issues"`
- `current?`
  - `issue_id`, `engagement_id`, `issue_type`, `issue_label`, `badge`, `created_at`
  - `target_label`, `context`
  - `fix_actions[]: {action_key, label, callback_family}`
  - `candidate_id`, `target_id`, `community_id`, `assigned_account_id`

Active issue types:

- `topics_not_chosen`
- `account_not_connected`
- `account_connecting`
- `sending_is_paused`
- `reply_expired`
- `reply_failed`
- `target_not_approved`
- `target_not_resolved`
- `community_permissions_missing`
- `rate_limit_active`
- `quiet_hours_active`
- `account_restricted`

### `GET /api/engagement/cockpit/engagements`

Response:

- `items[]`
  - `engagement_id`
  - `primary_label`
  - `community_label`
  - `sending_mode_label: "Draft" | "Auto send" | "Disabled"`
  - `issue_count`
  - `pending_task? {task_kind, label, count}`
  - `created_at`
- `total`, `offset`, `limit`

### `GET /api/engagement/cockpit/engagements/{engagement_id}`

Response:

- `engagement_id`
- `target_label`
- `topic_label?`
- `account_label?`
- `sending_mode_label`
- `approval_count`
- `issue_count`
- `pending_task? {task_kind, label, count, resume_callback}`

Pending-task routing:

- approvals -> `eng:appr:eng:{engagement_id}`
- approval updates -> `eng:appr:eng:{engagement_id}`
- issues -> `eng:iss:eng:{engagement_id}`

### `GET /api/engagement/cockpit/sent`

Response:

- `items[]: {action_id, message_text, community_label, sent_at}`
- `total`, `offset`, `limit`

Rules:

- only reply actions with `status = "sent"` appear
- non-reply actions do not appear

## Cockpit Mutations

### `POST /api/engagement/cockpit/drafts/{draft_id}/approve`

Response:

- `result: "approved" | "blocked" | "stale"`
- `message`
- `draft_id?`
- `engagement_id?`
- `next_callback?`
- `job_id?`
- `job_type?`
- `code?`

Rules:

- success queues `engagement.send`
- success returns:
  - `message = "Draft approved and send queued"`
  - `next_callback = "eng:appr:list:0"`
  - `job_type = "engagement.send"`
- stale reply opportunities do not block approval; only expired drafts and
  other candidate conflicts do
- active draft-update requests block approval with `code = "draft_not_reviewable"`

### `POST /api/engagement/cockpit/drafts/{draft_id}/reject`

- success returns `result = "rejected"` and `next_callback = "eng:appr:list:0"`
- only `needs_review` drafts can reject
- active draft-update requests block rejection with `code = "draft_not_reviewable"`

### `POST /api/engagement/cockpit/drafts/{draft_id}/edit`

Request:

- `edit_request: string(1..2000)`
- `requested_by?: string(1..200)`; route falls back to `"operator"`

Success:

- `result = "queued_update"`
- `message = "Updating draft"`
- `next_callback = "eng:appr:list:0"`

Blocking code:

- `edit_not_allowed`

### `POST /api/engagement/cockpit/issues/{issue_id}/actions/{action_key}`

Supported actions:

- wizard-entry: `chtopic`, `crtopic`, `chacct`, `swapacct`
- detail drill-ins: `ratelimit`, `quiet`
- semantic fixes: `resume`, `retry`, `apptgt`, `rsvtgt`, `fixperm`

Next-step callbacks:

- topic change/create -> `eng:wz:edit:{engagement_id}:topic`
- account change -> `eng:wz:edit:{engagement_id}:account`
- rate limit detail -> `eng:rate:open:{issue_id}`
- quiet hours -> `eng:quiet:open:{engagement_id}:{issue_id}`

Resolved actions:

- `resume` -> restore `active`/`suggest` state
- `retry` -> reopen failed candidate as `needs_review`
- `apptgt` -> approve target and sync allow flags
- `rsvtgt` -> enqueue `engagement_target.resolve`
- `fixperm` -> sync target/settings permission booleans

### `GET /api/engagement/cockpit/issues/{issue_id}/rate-limit`

Response:

- `result: "ready" | "stale"`
- `message`
- `next_callback`
- `issue_id?`, `engagement_id?`
- `title?`, `target_label?`, `blocked_action_label?`, `scope_label?`
- `reset_at?`

### `GET /api/engagement/cockpit/engagements/{engagement_id}/quiet-hours`
### `PUT /api/engagement/cockpit/engagements/{engagement_id}/quiet-hours`

Read response:

- `result: "ready" | "stale"`
- `message`
- `next_callback`
- `engagement_id?`
- `title?`
- `target_label?`
- `quiet_hours_enabled?`
- `quiet_hours_start?`
- `quiet_hours_end?`

Write request:

- `quiet_hours_enabled: bool`
- `quiet_hours_start?: HH:MM | null`
- `quiet_hours_end?: HH:MM | null`

Write response:

- `result: "updated" | "noop" | "blocked" | "stale"`
- `message`
- `next_callback`
- `engagement_id?`
- `quiet_hours_enabled?`
- `quiet_hours_start?`
- `quiet_hours_end?`
- `code?`

Write rules:

- enabling quiet hours requires both times
- unchanged writes return `result = "noop"`
- success routes back to `eng:iss:list:0`
- invalid enable writes use `code = "quiet_hours_invalid"`
