# Database Engagement

Active engagement database contract extracted from models, migrations, and
schema tests.

This doc is part of the extracted active contract set:

- `wiki/spec/api/engagement.md`
- `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`
- `wiki/spec/queue/job-types/engagement.md`
- `wiki/spec/database/engagement.md`

## Scope

This doc covers the live tables and invariants that back the active
task-first/cockpit engagement path.

Compat note:

- `community_engagement_settings` still exists and still participates in some
  effective-settings reads and schedulers, but it is not the primary task-first
  contract surface anymore.

## Core Tables

### `engagement_targets`

Purpose:

- operator-created allowlist rows for communities that may enter the engagement
  path

Key fields:

- `id`
- `community_id nullable`
- `submitted_ref`
- `submitted_ref_type`
  - `community_id`
  - `telegram_username`
  - `telegram_link`
  - `invite_link`
- `status`
  - `pending`
  - `resolved`
  - `approved`
  - `rejected`
  - `failed`
  - `archived`
- `allow_join`
- `allow_detect`
- `allow_post`
- `notes`
- `added_by`
- `approved_by`
- `approved_at`
- `last_error`
- `created_at`
- `updated_at`

Indexes:

- `ix_engagement_targets_community_id`
- `ix_engagement_targets_status`
- `ix_engagement_targets_submitted_ref`

Invariants:

- `community_id` is intentionally not unique
- multiple targets may point at the same community
- the active confirm path syncs `status` and `allow_*` from engagement settings
- deleting an active or historical engagement archives the target and clears all
  `allow_*` flags

### `engagements`

Purpose:

- first-class task-first engagement rows tied one-to-one to a target

Key fields:

- `id`
- `target_id`
- `community_id`
- `topic_id nullable`
- `status`
  - `draft`
  - `active`
  - `paused`
  - `archived`
- `name nullable`
- `created_by`
- `created_at`
- `updated_at`

Indexes and constraints:

- `UNIQUE (target_id)`
- `ix_engagements_community_id`
- `ix_engagements_status_created`

Invariants:

- one engagement row per target
- `topic_id` may stay `null` only while the engagement is still draft/resetting
- `archived` engagements remain durable so historical candidate/action records
  do not lose their lifecycle parent

### `engagement_settings`

Purpose:

- per-engagement send/join/account controls

Key fields:

- `id`
- `engagement_id`
- `mode`
  - `disabled`
  - `observe`
  - `suggest`
  - `require_approval`
  - `auto_limited`
- `allow_join`
- `allow_post`
- `reply_only`
- `require_approval`
- `max_posts_per_day`
- `min_minutes_between_posts`
- `quiet_hours_start nullable`
- `quiet_hours_end nullable`
- `assigned_account_id nullable`
- `created_at`
- `updated_at`

Defaults asserted by schema tests:

- `mode = "suggest"`
- `allow_join = false`
- `allow_post = false`
- `reply_only = true`
- `require_approval = true`
- `max_posts_per_day = 300`
- `min_minutes_between_posts = 1`

Indexes and constraints:

- `UNIQUE (engagement_id)`
- `ix_engagement_settings_engagement_id`

Task-first write-path invariants:

- rows are created lazily if missing
- task-first confirm sets:
  - `allow_join = true`
  - `allow_post = (mode == "auto_limited")`
- retry reset sets:
  - `assigned_account_id = null`
  - `mode = "disabled"`
  - `allow_join = false`
  - `allow_post = false`
- archive also forces:
  - `mode = "disabled"`
  - `allow_join = false`
  - `allow_post = false`

### `community_account_memberships`

Purpose:

- track which engagement account has joined which community

Key fields:

- `community_id`
- `telegram_account_id`
- `status`
  - `not_joined`
  - `join_requested`
  - `joined`
  - `failed`
  - `left`
  - `banned`
- `joined_at`
- `last_checked_at`
- `last_error`

Indexes and constraints:

- `UNIQUE (community_id, telegram_account_id)`
- `ix_community_account_memberships_community_account`

### `engagement_draft_update_requests`

Purpose:

- durable record for "request edit" approval mutations

Key fields:

- `engagement_id`
- `source_candidate_id`
- `replacement_candidate_id nullable`
- `status`
- `edit_request`
- `requested_by`
- `source_queue_created_at`
- `created_at`
- `updated_at`
- `completed_at nullable`

Indexes and constraints:

- `UNIQUE (source_candidate_id)`
- `UNIQUE (replacement_candidate_id)`
- `ix_engagement_draft_update_requests_engagement_status`
- `ix_engagement_draft_update_requests_queue_created`

Invariants:

- one active update request per source draft
- one replacement draft cannot belong to two update requests

## Candidate And Action Tables Used By The Active Cockpit

### `engagement_candidates`

Purpose:

- detected reply opportunities surfaced in approvals, issues, and send

Active fields:

- `community_id`
- `topic_id`
- `source_tg_message_id nullable`
- `source_reply_to_tg_message_id nullable`
- `source_excerpt nullable`
- `source_message_date nullable`
- `opportunity_kind`
  - `root`
  - `continuation`
- `root_candidate_id nullable`
- `conversation_key nullable`
- `detected_at`
- `detected_reason`
- `moment_strength`
- `timeliness`
- `reply_value`
- `suggested_reply nullable`
- `final_reply nullable`
- `status`
  - `needs_review`
  - `approved`
  - `rejected`
  - `sent`
  - `expired`
  - `failed`
- `reviewed_by`
- `reviewed_at`
- `review_deadline_at nullable`
- `reply_deadline_at`
- `operator_notified_at nullable`
- `expires_at`
- `created_at`
- `updated_at`

Indexes:

- `ix_engagement_candidates_status_created`
- `ix_engagement_candidates_community_topic_status`
- `ix_engagement_candidates_root_kind`

Invariants asserted by schema tests:

- cadence fields `source_reply_to_tg_message_id`, `opportunity_kind`,
  `root_candidate_id`, and `conversation_key` are present
- default `opportunity_kind = "root"`

### `engagement_actions`

Purpose:

- durable queue/send/join audit rows

Key fields:

- `candidate_id nullable`
- `community_id`
- `telegram_account_id`
- `action_type`
  - `join`
  - `reply`
  - `post`
  - `skip`
- `status`
  - `queued`
  - `sent`
  - `failed`
  - `skipped`
- `idempotency_key nullable`
- `outbound_text nullable`
- `reply_to_tg_message_id nullable`
- `sent_tg_message_id nullable`
- `scheduled_at nullable`
- `sent_at nullable`
- `error_message nullable`
- `created_at`
- `updated_at`

Indexes and constraints:

- `UNIQUE (idempotency_key)`
- `ix_engagement_actions_community_created`
- `ix_engagement_actions_account_created`

Active invariant:

- reply send idempotency is keyed as `engagement.send:{candidate_id}`

## Referenced Rows Required By The Active Path

### `engagement_topics`

- `engagement.topic_id` must reference an existing active topic row
- task-first patch/confirm both reject inactive or missing topics

### `telegram_accounts`

- task-first settings writes only accept accounts in the `engagement` pool
- banned accounts are rejected on write and surface as `account_restricted`
  issues

## Migration Guarantees

### `20260428_0013_task_first_engagements.py`

Creates:

- `engagements`
- `engagement_settings`

Backfill contract:

- scans `engagement_targets` with non-null `community_id`
- derives a single `topic_id` only when a community has exactly one distinct
  candidate topic
- creates one engagement per target if one does not already exist
- engagement status mapping:
  - target `archived` -> engagement `archived`
  - missing topic or missing legacy mode -> `draft`
  - target not approved -> `draft`
  - approved + legacy mode `disabled` -> `paused`
  - otherwise -> `active`
- copies any existing `community_engagement_settings` row into
  `engagement_settings`

### `20260428_0014_engagement_draft_update_requests.py`

Creates:

- `engagement_draft_update_requests`

Adds:

- unique source/replacement candidate constraints
- queue-created and engagement/status indexes

### `20260428_0015_engagement_target_duplicates.py`

Drops:

- the old unique constraint on `engagement_targets.community_id`

Guarantee:

- the same community may now back multiple engagement targets

### `20260430_0016_engagement_opportunity_cadence.py`

Adds to `engagement_candidates`:

- `source_reply_to_tg_message_id`
- `opportunity_kind`
- `root_candidate_id`
- `conversation_key`

Adds:

- self-FK on `root_candidate_id`
- index `ix_engagement_candidates_root_kind`
