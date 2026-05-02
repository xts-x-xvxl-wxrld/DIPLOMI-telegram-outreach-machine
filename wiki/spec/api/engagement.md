# API Engagement

Engagement target, settings, topic, prompt, style, candidate, action, and rollout endpoint contracts.

## Engagement

Engagement endpoints are optional/future. They must remain operator-controlled and separate from
discovery snapshots and analysis.

Backend model rule:

- engagement is a first-class backend entity
- the chosen topic, assigned account, sending mode, and pending-task state belong
  to an engagement record
- older community-scoped settings endpoints remain compatibility paths until the
  engagement-scoped write surface is complete

Operator terminology rule:

- operator-facing copy should prefer `reply opportunity` and `draft`
- legacy backend/storage names such as `candidate` and `candidate_id` may
  remain in implementation-facing APIs until a later rename

Wizard write model rule:

- use a hybrid contract for the wizard
- draft step data writes go through generic engagement endpoints
- workflow-edge actions stay semantic through `wizard-confirm` and
  `wizard-retry`

## Migration Contract

The task-first cockpit must cut over from community-scoped engagement controls
to engagement-scoped read and write paths without exposing mixed models to the
operator.

Migration rules:

- new task-first bot surfaces read only from engagement-scoped cockpit endpoints
- the bot must not merge community-scoped settings reads into new home, queue,
  detail, or sent-message screens
- engagement-scoped writes become the primary mutation surface for wizard,
  pending-task, and issue-fix flows
- older community-scoped settings routes remain temporary compatibility paths
  for legacy screens and internal backfills only
- once a bot surface is migrated, it must stop emitting callbacks that depend on
  community-scoped engagement settings screens

Compatibility boundaries:

- `GET /api/communities/{community_id}/engagement-settings` may remain available
  for legacy admin/review screens, but it is not a source for the new cockpit
- `PUT /api/communities/{community_id}/engagement-settings` may remain available
  during migration, but new wizard saves should write through
  `PUT /api/engagements/{engagement_id}/settings`
- legacy candidate, target, and settings screens may continue to call older
  low-level mutation routes until their task-first replacements ship
- task-first issue actions should call semantic cockpit mutations even when the
  backend temporarily implements them by adapting to older internal services

Adapter rules:

- if legacy data exists only at the community scope, backend migration code may
  seed or update an engagement record from that state before serving the new
  cockpit
- one active engagement per target is the migration baseline; do not infer or
  auto-create multiple engagement variants for one community during the first
  cutover
- topic choice, assigned account, sending mode, quiet hours, and approval
  settings must end up persisted against the engagement record
- background migration or on-read backfill must be idempotent

Cutover sequence:

1. ship engagement tables and engagement-scoped write endpoints
2. backfill or create engagement records for existing approved community-level
   setups
3. ship cockpit read-model endpoints backed only by engagement-scoped state
4. migrate wizard, detail, approvals, issues, and sent-message bot routes to
   the new cockpit endpoints and callbacks
5. retire legacy community-settings navigation from the operator cockpit
6. remove community-scoped engagement-settings writes after no active bot route
   depends on them

Operator-facing safety rules:

- do not show both legacy community settings screens and the new task-first
  cockpit entry points as parallel primary paths
- if a legacy row has not yet been migrated into an engagement record, create or
  backfill it before opening the new wizard/detail flow instead of showing a
  partial screen
- if migration cannot produce a valid engagement record, fail closed with a
  short operator-facing error and no silent fallback to raw legacy settings

Engagement target, prompt-profile, style-rule, topic, and community engagement-settings mutation
routes are operator-facing setup controls. They should be available to any Telegram user who is
already authorized to use the bot; there is no separate engagement-admin mutation boundary at this
time.

### `GET /api/engagement/targets`

Lists manual engagement targets. Targets are the explicit engagement allowlist and are separate from
seed groups, direct handle intakes, and community review.

Query parameters:

- `status`
- `limit`
- `offset`

### `GET /api/engagements`

Lists first-class engagement records.

### `POST /api/engagements`

Creates a draft engagement tied to an existing target.

Request:

```json
{
  "target_id": "uuid",
  "created_by": "telegram_user_id_or_operator"
}
```

Rules:

- return the existing draft or active engagement for that target instead of
  creating duplicates
- do not activate the engagement from this route
- incomplete draft engagements may exist off-list until final confirmation

### `GET /api/engagements/{engagement_id}`

Returns one engagement record with target, community, status, and high-level
operator fields.

### `PATCH /api/engagements/{engagement_id}`

Updates engagement-level fields such as name or status.

Request DTO:

```json
{
  "topic_id": "uuid-or-null",
  "name": "optional display name"
}
```

Wizard use:

- use this route for draft-level engagement fields that belong directly on the
  engagement row, including `topic_id`
- this is a generic field-write route, not a commit route
- partial draft writes are allowed while `status = draft`
- active-engagement edits should still validate the full resulting state before
  final confirmation succeeds

Field rules:

- `topic_id` sets the one chosen topic for the engagement
- `topic_id = null` is allowed only while the engagement remains a draft or the
  wizard is being reset
- do not accept arrays or multi-topic payloads on this route
- omit unchanged fields instead of requiring full-row replacement

Response DTO:

```json
{
  "result": "updated",
  "engagement": {
    "id": "uuid",
    "status": "draft",
    "topic_id": "uuid-or-null",
    "name": "optional display name"
  }
}
```

`result` values:

- `updated` — patch accepted
- `blocked` — patch is syntactically valid but not allowed in current state
- `stale` — engagement no longer exists or changed incompatibly

`blocked` shape:

```json
{
  "result": "blocked",
  "message": "This engagement cannot change topic right now",
  "code": "topic_edit_blocked"
}
```

### `PUT /api/engagements/{engagement_id}/settings`

Creates or updates engagement-scoped settings.

Request DTO:

```json
{
  "assigned_account_id": "uuid-or-null",
  "mode": "suggest",
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "07:00"
}
```

Wizard use:

- step 3 and step 4 writes may pass through this route for assigned account and
  sending mode settings
- this is a generic field-write route, not a commit route
- writes must be idempotent so wizard reopen and retry paths can safely repeat
  them

Field rules:

- `assigned_account_id` is the wizard-owned account selection field
- `mode` accepts wizard-backed values `suggest` and `auto_limited`
- `quiet_hours_start` and `quiet_hours_end` are optional and usually edited
  outside the initial add flow
- if one quiet-hours field is present, both must be present
- omit unchanged fields instead of requiring the caller to resend locked MVP
  defaults

Response DTO:

```json
{
  "result": "updated",
  "settings": {
    "engagement_id": "uuid",
    "assigned_account_id": "uuid-or-null",
    "mode": "suggest",
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00"
  }
}
```

`result` values:

- `updated` — write accepted
- `blocked` — write is valid but cannot be applied
- `stale` — engagement no longer exists or settings state changed underneath the
  caller

`blocked` shape:

```json
{
  "result": "blocked",
  "message": "This account cannot be used here",
  "code": "account_unusable"
}
```

### `POST /api/engagements/{engagement_id}/wizard-confirm`

Validates a draft or edited engagement and commits it as the final wizard
result.

Rules:

- confirm must validate presence of target, topic, joined account, and sending
  mode
- confirm is the only wizard route that may commit the full staged draft as an
  operator-visible completed engagement
- for draft engagements, confirm may activate the engagement and approve the
  target when needed
- for existing active engagements opened in edit mode, confirm updates the
  current engagement atomically instead of creating a new one
- detect-job enqueue and activation must be treated as one operator-facing
  confirmation result

Response DTO:

```json
{
  "result": "confirmed",
  "message": "Engagement started",
  "engagement_id": "uuid",
  "engagement_status": "active",
  "target_status": "approved",
  "next_callback": "eng:det:open:uuid"
}
```

`result` values:

- `confirmed` — confirm succeeded and the bot should route to `next_callback`
- `validation_failed` — required wizard state is missing or invalid
- `blocked` — confirm is well-formed but cannot complete right now
- `stale` — the engagement or dependent state changed underneath the wizard

`validation_failed` shape:

```json
{
  "result": "validation_failed",
  "message": "Choose a topic",
  "field": "topic",
  "next_callback": "eng:wz:edit:uuid:topic"
}
```

Allowed `field` values:

- `target`
- `topic`
- `account`
- `mode`

`blocked` shape:

```json
{
  "result": "blocked",
  "message": "Account is not connected",
  "code": "account_not_joined",
  "next_callback": "eng:wz:edit:uuid:account"
}
```

Recommended `code` values:

- `target_not_resolved`
- `target_not_approved`
- `topic_missing`
- `account_missing`
- `account_not_joined`
- `sending_mode_missing`
- `detect_enqueue_failed`
- `engagement_archived`

`stale` shape:

```json
{
  "result": "stale",
  "message": "This engagement changed. Review it again.",
  "next_callback": "eng:det:open:uuid"
}
```

### `POST /api/engagements/{engagement_id}/wizard-retry`

Clears wizard-owned draft choices and resets the engagement setup flow to step
1 without deleting the durable engagement record.

Rules:

- retry is a semantic reset action, not a generic field patch
- clear `topic_id`
- clear assigned account if one was only chosen for the abandoned wizard flow
- reset sending-mode-backed engagement settings to an unconfigured draft state
- keep the target reference so idempotent restart can reuse the same draft row

Response DTO:

```json
{
  "result": "reset",
  "message": "Start again",
  "engagement_id": "uuid",
  "next_callback": "eng:wz:start"
}
```

`result` values:

- `reset` — wizard-owned draft state cleared and flow should restart
- `blocked` — retry cannot reset safely right now
- `stale` — engagement no longer exists or is no longer a resettable draft

`blocked` shape:

```json
{
  "result": "blocked",
  "message": "This engagement is already active",
  "code": "engagement_active",
  "next_callback": "eng:det:open:uuid"
}
```

Recommended `code` values:

- `engagement_active`
- `engagement_archived`
- `reset_not_allowed`

`stale` shape:

```json
{
  "result": "stale",
  "message": "This draft is no longer available",
  "next_callback": "op:add"
}
```

### `POST /api/engagements/{engagement_id}/activate`

Legacy low-level activation route.

Rules:

- the task-first wizard should use `wizard-confirm` instead of calling this
  route directly
- this route may remain temporarily for compatibility or internal services

### `GET /api/engagement/targets/{target_id}`

Returns one manual engagement target with submitted reference, resolved community fields when
available, status, permissions, notes, approval metadata, and last error.

### `POST /api/engagement/targets`

Creates a new engagement target from an existing `community_id`, public Telegram username, or
public Telegram link.

Request:

```json
{
  "target_ref": "@example",
  "notes": "Manual engagement candidate",
  "added_by": "telegram_user_id_or_operator"
}
```

Rules:

- Existing `community_id` targets are created as `resolved`.
- Public username/link targets are created as `pending` and must be resolved by an engagement job.
- Normalized public refs are stored canonically, but repeated submissions still create a new
  engagement-target row instead of reusing an older one.
- Private invite-link resolution remains out of scope for MVP.

### `PATCH /api/engagement/targets/{target_id}`

Updates target status, notes, and engagement permissions.

Request:

```json
{
  "status": "approved",
  "allow_join": true,
  "allow_detect": true,
  "allow_post": false,
  "updated_by": "telegram_user_id_or_operator"
}
```

Rules:

- A target must resolve to a community before it can be approved.
- Rejected and archived targets force `allow_join`, `allow_detect`, and `allow_post` to false.
- Approving a target records `approved_by` and `approved_at`.

### `POST /api/engagement/targets/{target_id}/resolve-jobs`

Queues `engagement_target.resolve`. This is an engagement job, not a seed job.

Request:

```json
{
  "requested_by": "telegram_user_id_or_operator|null"
}
```

### `POST /api/engagement/targets/{target_id}/join-jobs`

Queues `community.join` for the target's resolved community. The worker still enforces target
approval and `allow_join`.

### `POST /api/engagement/targets/{target_id}/detect-jobs`

Queues manual `engagement.detect` for the target's resolved community. The worker still enforces
target approval and `allow_detect`.

### `GET /api/communities/{community_id}/engagement-settings`

Returns engagement settings for one community. If no settings exist, engagement is disabled.

### `PUT /api/communities/{community_id}/engagement-settings`

Creates or updates per-community engagement settings.

Request:

```json
{
  "mode": "suggest",
  "allow_join": true,
  "allow_post": false,
  "reply_only": true,
  "require_approval": true,
  "max_posts_per_day": 1,
  "min_minutes_between_posts": 240
}
```

MVP rules:

- `require_approval` must remain true.
- `reply_only` must remain true.
- Settings are disabled unless explicitly created or enabled.

### `POST /api/communities/{community_id}/join-jobs`

Queues `community.join` after verifying the community exists. The API does not call Telethon
directly.

Request:

```json
{
  "telegram_account_id": "uuid-or-null",
  "requested_by": "telegram_user_id_or_operator|null"
}
```

Response `202`:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "community.join",
    "status": "queued"
  }
}
```

### `GET /api/engagement/topics`

Lists configured engagement topics.

### `GET /api/engagement/topics/{topic_id}`

Returns one engagement topic with guidance, trigger keywords, negative keywords, and ordered good
and bad example arrays.

### `POST /api/engagement/topics`

Creates an engagement topic.

### `PATCH /api/engagement/topics/{topic_id}`

Updates an engagement topic.

### `POST /api/engagement/topics/{topic_id}/examples`

Adds a good or bad reply example to a topic. Good examples are positive guidance; bad examples are
negative examples only and must not be copied as reply templates.

### `DELETE /api/engagement/topics/{topic_id}/examples/{example_type}/{index}`

Removes a topic example by ordered array index. `example_type` is `good` or `bad`.

### `GET /api/engagement/prompt-profiles`

Lists admin-managed engagement prompt profiles with current immutable version metadata.

### `POST /api/engagement/prompt-profiles`

Creates a prompt profile and version 1. Fields include name, model, temperature,
max_output_tokens, system_prompt, user_prompt_template, output_schema_name, active, and created_by.

### `GET /api/engagement/prompt-profiles/{profile_id}`

Returns one prompt profile with current version metadata, model parameters, output schema, capped
bot-safe prompt preview fields, active state, and audit metadata.

### `PATCH /api/engagement/prompt-profiles/{profile_id}`

Updates editable prompt profile fields and creates a new immutable version row.

### `POST /api/engagement/prompt-profiles/{profile_id}/activate`

Activates one prompt profile and deactivates other active profiles.

### `POST /api/engagement/prompt-profiles/{profile_id}/duplicate`

Copies an existing prompt profile into a new inactive profile with a new name and version 1.

### `POST /api/engagement/prompt-profiles/{profile_id}/rollback`

Restores a selected immutable version into the current profile state and creates a new current
version representing that rollback.

### `POST /api/engagement/prompt-profiles/{profile_id}/preview`

Renders the prompt template with approved variables only. This endpoint does not call OpenAI.

### `GET /api/engagement/prompt-profiles/{profile_id}/versions`

Lists immutable prompt profile versions newest first.

### `GET /api/engagement/style-rules`

Lists style rules by optional scope, scope ID, active state, limit, and offset.

### `GET /api/engagement/style-rules/{rule_id}`

Returns one style rule with scope, scope ID, active state, priority, rule text, and update
metadata.

### `POST /api/engagement/style-rules`

Creates a global, account, community, or topic style rule.

### `PATCH /api/engagement/style-rules/{rule_id}`

Updates style rule text, priority, scope, or active state.

### `POST /api/communities/{community_id}/engagement-detect-jobs`

Queues `engagement.detect`.

### `GET /api/engagement/candidates`

Lists candidate replies for operator review.

Query parameters:

- `status` - default `needs_review`
- `community_id`
- `topic_id`
- `limit`
- `offset`

## Task-First Cockpit Read Models

The task-first Telegram cockpit should not have to assemble its primary screens
from a mix of low-level candidate, action, target, and settings endpoints.

Add explicit read-model endpoints for the task-first surfaces:

```http
GET /api/engagement/cockpit/home
GET /api/engagement/cockpit/approvals
GET /api/engagement/cockpit/issues
GET /api/engagement/cockpit/engagements
GET /api/engagement/cockpit/engagements/{engagement_id}
GET /api/engagement/cockpit/sent
```

These are read-model endpoints only. Existing candidate, target, settings, and
action mutation endpoints remain the write path.

### `GET /api/engagement/cockpit/home`

Returns the home summary state for `Engagements`.

Response:

```json
{
  "state": "approvals",
  "draft_count": 2,
  "issue_count": 1,
  "active_engagement_count": 3,
  "has_sent_messages": true,
  "next_draft_preview": {
    "draft_id": "uuid",
    "engagement_id": "uuid",
    "text_preview": "draft text trimmed for home preview",
    "target_label": "Open-source CRM · @example",
    "why": "Matched topic: CRM",
    "updated": false
  },
  "latest_issue_preview": {
    "issue_id": "uuid",
    "engagement_id": "uuid",
    "issue_type": "topics_not_chosen",
    "issue_label": "Topics not chosen",
    "badge": "Skipped before",
    "created_at": "iso_datetime"
  }
}
```

Rules:

- `state` is one of `first_run`, `approvals`, `issues`, or `clear`.
- `next_draft_preview` is `null` when no drafts are waiting.
- `latest_issue_preview` is `null` when no issues exist.
- `active_engagement_count` is omitted only if the product explicitly decides to
  derive it elsewhere; otherwise include it here so the bot can render the
  clear-state summary directly.

### `GET /api/engagement/cockpit/approvals`

Returns the controller payload for `Approve draft`.

Response:

```json
{
  "queue_count": 2,
  "updating_count": 1,
  "empty_state": "none",
  "placeholders": [
    {
      "slot": 0,
      "label": "Updating draft"
    }
  ],
  "current": {
    "draft_id": "uuid",
    "engagement_id": "uuid",
    "target_label": "Open-source CRM · @example",
    "text": "full draft text",
    "why": "Matched topic: CRM",
    "badge": "Updated draft"
  }
}
```

Rules:

- `empty_state` is one of `none`, `waiting_for_updates`, or `no_drafts`.
- `current` is `null` only when no actionable draft is available.
- Placeholder order must preserve original queue order.

### `GET /api/engagement/cockpit/engagements/{engagement_id}/approvals`

Returns the scoped controller payload for `Approve draft` for one engagement.

Response:

- same DTO shape as `GET /api/engagement/cockpit/approvals`

Rules:

- filter the queue to drafts for the requested engagement only
- use the same `empty_state` contract as the global approvals controller
- when no drafts remain for that engagement, the bot may return to engagement
  detail instead of leaving the operator on an empty scoped queue

### `POST /api/engagement/cockpit/drafts/{draft_id}/approve`

Approves the current draft from the task-first approval queue.

Rules:

- this is the operator-facing semantic approval route for `Approve draft`
- backend may implement it by adapting to lower-level candidate approval
  services
- approval uses edited reply text when one already exists; otherwise it uses the
  current suggested draft text

Response DTO:

```json
{
  "result": "approved",
  "message": "Draft approved",
  "draft_id": "uuid",
  "next_callback": "eng:appr:list:0"
}
```

`result` values:

- `approved` — approval succeeded
- `blocked` — draft exists but cannot be approved right now
- `stale` — draft is no longer reviewable

`blocked` shape:

```json
{
  "result": "blocked",
  "message": "Couldn't approve draft",
  "code": "draft_not_reviewable"
}
```

Recommended `code` values:

- `draft_not_reviewable`
- `draft_expired`
- `engagement_paused`

### `POST /api/engagement/cockpit/drafts/{draft_id}/reject`

Rejects the current draft from the task-first approval queue.

Rules:

- this is the operator-facing semantic reject route for `Approve draft`
- rejection removes the draft from the active approval queue

Response DTO:

```json
{
  "result": "rejected",
  "message": "Draft rejected",
  "draft_id": "uuid",
  "next_callback": "eng:appr:list:0"
}
```

`result` values:

- `rejected` — reject succeeded
- `blocked` — draft exists but cannot be rejected right now
- `stale` — draft is no longer reviewable

`blocked` shape:

```json
{
  "result": "blocked",
  "message": "Couldn't reject draft",
  "code": "draft_not_reviewable"
}
```

### `POST /api/engagement/cockpit/drafts/{draft_id}/edit`

Accepts operator edit guidance and queues a replacement draft.

Request DTO:

```json
{
  "edit_request": "Make it shorter and less salesy"
}
```

Rules:

- this route should not overwrite the current approved candidate text in place
- it should queue replacement-draft generation and convert the current queue
  slot into an `Updating draft` placeholder
- when the replacement draft is ready, it should re-enter the approval queue as
  an `Updated draft`

Response DTO:

```json
{
  "result": "queued_update",
  "message": "Updating draft",
  "draft_id": "uuid",
  "engagement_id": "uuid",
  "next_callback": "eng:appr:list:0"
}
```

`result` values:

- `queued_update` — replacement-draft generation was accepted
- `blocked` — edit request is valid but cannot be queued
- `stale` — draft is no longer reviewable

`blocked` shape:

```json
{
  "result": "blocked",
  "message": "Couldn't update draft",
  "code": "edit_not_allowed"
}
```

### `GET /api/engagement/cockpit/issues`

Returns the controller payload for `Top issues`.

Response:

```json
{
  "queue_count": 3,
  "empty_state": "none",
  "current": {
    "issue_id": "uuid",
    "engagement_id": "uuid",
    "issue_type": "topics_not_chosen",
    "issue_label": "Topics not chosen",
    "badge": "Skipped before",
    "created_at": "iso_datetime",
    "fix_actions": [
      {
        "action_key": "chtopic",
        "label": "Choose topic",
        "callback_family": "eng:wz"
      },
      {
        "action_key": "crtopic",
        "label": "Create topic",
        "callback_family": "eng:wz"
      }
    ]
  }
}
```

### `GET /api/engagement/cockpit/engagements/{engagement_id}/issues`

Returns the scoped controller payload for `Top issues` for one engagement.

Response:

- same DTO shape as `GET /api/engagement/cockpit/issues`

Rules:

- filter the queue to issues for the requested engagement only
- use the same `empty_state` contract as the global issues controller
- when no issues remain for that engagement, the bot may return to engagement
  detail instead of leaving the operator on an empty scoped queue

Rules:

- `empty_state` is one of `none` or `no_issues`.
- `fix_actions` may be empty.
- `issue_type` is the stable machine key; `issue_label` is the operator-facing
  copy.
- only one active issue of a given type may exist per engagement at a time.
- when an issue condition resolves, it disappears immediately from this payload.
- when the same condition happens again later, it returns as a new issue with a
  fresh `created_at`.

Each issue item should also carry the domain IDs needed for safe mutation, such
as `candidate_id`, `target_id`, `community_id`, and `assigned_account_id` when
applicable.

Generation rules:

- `topics_not_chosen` — completed engagement has no chosen topic
- `account_not_connected` — no usable joined engagement account
- `sending_is_paused` — engagement is paused or disabled and would otherwise be
  eligible to run
- `reply_expired` — reply opportunity reached `expired`
- `reply_failed` — reply opportunity reached `failed` and is retryable
- `target_not_approved` — target exists but is not approved
- `target_not_resolved` — target intake not yet resolved to a usable community
- `community_permissions_missing` — target/settings permissions do not satisfy
  the engagement's current sending mode
- `rate_limit_active` — a real engagement action is currently blocked by rate
  limiting
- `quiet_hours_active` — a real engagement action is currently blocked by quiet
  hours
- `account_restricted` — assigned or selected engagement account is unusable

Do not emit passive non-actionable blockers for `rate_limit_active` or
`quiet_hours_active` when no real action is currently blocked.

### `POST /api/engagement/cockpit/issues/{issue_id}/actions/{action_key}`

Semantic mutation layer for issue-resolution actions.

This endpoint validates that the issue still exists, performs the mutation when
the action is one-tap safe, or returns the next guided step when operator input
is still required.

Response:

```json
{
  "result": "resolved",
  "message": "Target approved",
  "next_callback": "eng:iss:list:0"
}
```

Rules:

- `result` is one of `resolved`, `next_step`, `noop`, `stale`, or `blocked`.
- `next_callback` is required for `next_step` and may also be returned for
  `resolved` when the backend wants the bot to refresh a specific controller.
- The bot should route from this response instead of inferring the next action
  itself.

Action handling:

- `chtopic` — return `next_step` to `eng:wz:edit:<engagement_id>:topic`
- `crtopic` — return `next_step` to `eng:wz:edit:<engagement_id>:topic`
- `chacct` — return `next_step` to `eng:wz:edit:<engagement_id>:account`
- `swapacct` — return `next_step` to `eng:wz:edit:<engagement_id>:account`
- `resume` — direct semantic resume-sending mutation
- `retry` — call existing `POST /api/engagement/candidates/{candidate_id}/retry`
- `apptgt` — direct semantic target-approve mutation
- `rsvtgt` — call existing `POST /api/engagement/targets/{target_id}/resolve-jobs`
- `fixperm` — direct semantic permission-sync mutation
- `ratelimit` — return `next_step` to read-only rate-limit detail
- `quiet` — return `next_step` to quiet-hours editing

Recommended semantic helper mutations:

```http
POST /api/engagement/targets/{target_id}/approve
POST /api/engagement/cockpit/engagements/{engagement_id}/resume
POST /api/engagement/cockpit/engagements/{engagement_id}/fix-permissions
```

### `GET /api/engagement/cockpit/issues/{issue_id}/rate-limit`

Returns the read-only detail payload for `Rate limit active`.

Response DTO:

```json
{
  "result": "ready",
  "issue_id": "uuid",
  "engagement_id": "uuid",
  "title": "Rate limit active",
  "target_label": "Open-source CRM · @example",
  "blocked_action_label": "Send reply",
  "scope_label": "Account limit",
  "message": "Sending is paused until the limit clears.",
  "reset_at": "iso_datetime_or_null",
  "next_callback": "eng:iss:open:uuid"
}
```

`result` values:

- `ready` — detail payload is available
- `stale` — issue is no longer active

`stale` shape:

```json
{
  "result": "stale",
  "message": "Rate limit is no longer active",
  "next_callback": "eng:iss:list:0"
}
```

Rules:

- `reset_at` may be `null` when no exact reset time is known
- this endpoint is read-only; it does not mutate engagement state
- `next_callback` should return to the issue card or controller, not to home

### `GET /api/engagement/cockpit/engagements/{engagement_id}/quiet-hours`

Returns the edit payload for `Change quiet hours`.

Response DTO:

```json
{
  "result": "ready",
  "engagement_id": "uuid",
  "title": "Change quiet hours",
  "target_label": "Open-source CRM · @example",
  "message": "Quiet hours are blocking the engagement right now.",
  "quiet_hours_enabled": true,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "07:00",
  "next_callback": "eng:iss:open:uuid"
}
```

`result` values:

- `ready` — quiet-hours edit payload is available
- `stale` — quiet-hours issue is no longer active or the engagement no longer
  has editable quiet-hours state

`stale` shape:

```json
{
  "result": "stale",
  "message": "Quiet hours no longer need changes",
  "next_callback": "eng:iss:list:0"
}
```

Rules:

- `quiet_hours_enabled = false` is allowed for surfaces that expose a pure
  “turn off” state
- if quiet hours are configured, both `quiet_hours_start` and
  `quiet_hours_end` must be present
- this endpoint is for screen rendering; save uses the write endpoint below

### `PUT /api/engagement/cockpit/engagements/{engagement_id}/quiet-hours`

Saves or clears quiet hours for one engagement.

Request DTO:

```json
{
  "quiet_hours_enabled": true,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "07:00"
}
```

Turn-off request:

```json
{
  "quiet_hours_enabled": false
}
```

Rules:

- when `quiet_hours_enabled = true`, both `quiet_hours_start` and
  `quiet_hours_end` are required
- when `quiet_hours_enabled = false`, start and end must be cleared
- this is the task-first quiet-hours mutation route; bot handlers should not
  patch quiet-hours fields through unrelated generic settings writes

Response DTO:

```json
{
  "result": "updated",
  "message": "Quiet hours updated",
  "engagement_id": "uuid",
  "quiet_hours_enabled": true,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "07:00",
  "next_callback": "eng:iss:list:0"
}
```

`result` values:

- `updated` — quiet hours saved or cleared
- `noop` — submitted values match current values
- `blocked` — request is valid but cannot be applied
- `stale` — engagement or issue state changed underneath the editor

`noop` shape:

```json
{
  "result": "noop",
  "message": "No quiet-hours changes",
  "next_callback": "eng:iss:open:uuid"
}
```

`blocked` shape:

```json
{
  "result": "blocked",
  "message": "Couldn't update quiet hours",
  "code": "quiet_hours_invalid"
}
```

Recommended `code` values:

- `quiet_hours_invalid`
- `quiet_hours_edit_blocked`
- `engagement_archived`

These keep the bot away from raw low-level `PATCH` payload construction for
status and permission fields.

### `GET /api/engagement/cockpit/engagements`

Returns the list payload for `My engagements`.

Response:

```json
{
  "items": [
    {
      "engagement_id": "uuid",
      "primary_label": "CRM replies",
      "community_label": "@example",
      "sending_mode_label": "Draft",
      "issue_count": 1,
      "pending_task": {
        "task_kind": "issues",
        "label": "Top issues",
        "count": 1
      },
      "created_at": "iso_datetime"
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 20
}
```

Rules:

- Items are ordered newest first.
- Incomplete engagements are excluded.
- `issue_count` is `0` when no issue badge should show.
- `pending_task` is `null` when none exists.
- default page size is 20 unless the caller explicitly requests another limit.

### `GET /api/engagement/cockpit/engagements/{engagement_id}`

Returns the detail payload for one engagement.

Response:

```json
{
  "engagement_id": "uuid",
  "target_label": "@example",
  "topic_label": "CRM replies",
  "account_label": "+ENGAGEMENT-1",
  "sending_mode_label": "Draft",
  "approval_count": 2,
  "issue_count": 1,
  "pending_task": {
    "task_kind": "approvals",
    "label": "Approve draft",
    "count": 2,
    "resume_callback": "eng:appr:eng:uuid"
  }
}
```

Rules:

- `pending_task` is `null` when no main action should show.
- `pending_task.task_kind` is one of `approvals`, `approval_updates`, or `issues`.
- `pending_task.label` is `Approve draft` for `approvals` and
  `approval_updates`, and `Top issues` for `issues`.
- `pending_task.count` is the scoped count for that engagement and task kind.
- if multiple pending-task kinds exist, the backend returns only the
  highest-priority one:
  1. `approvals`
  2. `approval_updates`
  3. `issues`
- `resume_callback` points to the callback target, not a UI label.
- `resume_callback` should use the scoped queue controller for that engagement,
  such as `eng:appr:eng:<engagement_id>` or `eng:iss:eng:<engagement_id>`.

### `GET /api/engagement/cockpit/sent`

Returns the read-only feed payload for `Sent messages`.

Response:

```json
{
  "items": [
    {
      "action_id": "uuid",
      "message_text": "public reply text",
      "community_label": "@example",
      "sent_at": "iso_datetime"
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 20
}
```

Rules:

- Items are ordered newest first.
- `sent_at` is absolute time rendered in the operator's local timezone, not
  relative text.
- default page size is 20 unless the caller explicitly requests another limit.

### `GET /api/engagement/candidates/{candidate_id}`

Returns one candidate reply detail for bot review. The response uses the same safe candidate fields
as the candidate list: community/topic labels, capped source excerpt, detected reason, suggested
reply, final reply, prompt provenance, risk notes, status, review metadata, expiry, and timestamps.
It must not expose sender identity, phone numbers, private account metadata, or person-level scores.

### `GET /api/engagement/candidates/{candidate_id}/revisions`

Returns immutable manual reply revision history newest first.

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "candidate_id": "uuid",
      "revision_number": 1,
      "reply_text": "edited final public reply",
      "edited_by": "telegram:123",
      "edit_reason": "manual edit",
      "created_at": "iso_datetime"
    }
  ],
  "total": 1
}
```

### `POST /api/engagement/candidates/{candidate_id}/approve`

Approves a candidate reply. The API records the reviewer and review timestamp. Sending still happens
through `engagement.send`.

If an edited `final_reply` already exists, approval uses that text. If no edit exists, approval
falls back to the generated `suggested_reply`.

### `POST /api/engagement/candidates/{candidate_id}/edit`

Stores an edited final reply, creates an immutable candidate revision row, and keeps the candidate in
review until explicitly approved.

### `POST /api/engagement/candidates/{candidate_id}/reject`

Rejects a candidate reply.

### `POST /api/engagement/candidates/{candidate_id}/expire`

Explicitly expires a reviewable candidate so it leaves the active review/send queue. Sent, rejected,
and already expired candidates are not expirable.

### `POST /api/engagement/candidates/{candidate_id}/retry`

Reopens a failed candidate for review when it has not expired. Other statuses are rejected.

### `POST /api/engagement/candidates/{candidate_id}/send-jobs`

Queues `engagement.send` for an approved candidate.

### `GET /api/engagement/actions`

Lists outbound action audit rows.

Query parameters:

- `community_id`
- `candidate_id`
- `status`
- `action_type`
- `limit`
- `offset`

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "candidate_id": "uuid-or-null",
      "community_id": "uuid",
      "telegram_account_id": "uuid",
      "action_type": "reply",
      "status": "sent",
      "outbound_text": "exact approved public reply",
      "reply_to_tg_message_id": 123,
      "sent_tg_message_id": 456,
      "scheduled_at": "iso_datetime|null",
      "sent_at": "iso_datetime|null",
      "error_message": null,
      "created_at": "iso_datetime"
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

Rules:

- API handlers must not call Telethon directly.
- API responses must not expose phone numbers.
- API responses must not expose person-level scores.
- Engagement workers fail closed unless at least one approved engagement target for the community
  grants the matching join/detect/post permission.
- Audit rows should remain available for operator review.

### `GET /api/engagement/semantic-rollout`

Returns aggregate semantic-selector rollout outcomes for threshold tuning.

Query parameters:

- `window_days` - default `14`, range `1..90`
- `community_id` - optional community filter
- `topic_id` - optional topic filter

Response:

```json
{
  "window_days": 14,
  "community_id": null,
  "topic_id": null,
  "total_semantic_candidates": 3,
  "reviewed_semantic_candidates": 2,
  "pending": 1,
  "approved": 1,
  "rejected": 1,
  "expired": 0,
  "approval_rate": 0.5,
  "bands": [
    {
      "label": "0.80-0.89",
      "min_similarity": 0.8,
      "max_similarity": 0.9,
      "total": 1,
      "pending": 0,
      "approved": 1,
      "rejected": 0,
      "expired": 0,
      "approval_rate": 1.0,
      "average_similarity": 0.83
    }
  ]
}
```

Rules:

- The endpoint reads compact semantic metadata already stored on reply opportunities.
- Output is aggregate-only. It must not expose source excerpts, sender identity, candidate IDs,
  phone numbers, or person-level scores.
