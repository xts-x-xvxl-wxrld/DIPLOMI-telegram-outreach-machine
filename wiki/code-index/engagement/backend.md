# Engagement Backend Map

## Scope

This shard covers backend ownership for engagement routes, services, shared
views, and queue seams.

## Read First

- `backend/api/routes/engagement.py`
- `backend/api/routes/engagement_task_first.py`
- `backend/api/routes/engagement_cockpit.py`
- `backend/services/task_first_engagements.py`
- `backend/services/task_first_engagement_cockpit.py`
- `backend/services/task_first_engagement_cockpit_mutations.py`
- `backend/services/task_first_engagement_issues.py`
- `backend/services/community_engagement.py`

## Active

### Router composition

- `backend/api/routes/engagement.py`
  - combined engagement router
  - includes task-first, cockpit, and older community-scoped shards
  - rebinds queue/service dependencies into those shard modules

### Task-first write path

- `backend/api/routes/engagement_task_first.py`
  - create draft engagement
  - patch engagement fields
  - write per-engagement settings
  - confirm wizard state
  - retry incomplete setup
- `backend/services/task_first_engagements.py`
  - `TaskFirstEngagementView`, `TaskFirstEngagementSettingsView`
  - `create_task_first_engagement`
  - `patch_task_first_engagement`
  - `put_task_first_engagement_settings`
  - `confirm_task_first_engagement`
  - `retry_task_first_engagement`
  - promotion bridge from target/community data into first-class engagement rows

### Task-first cockpit read path

- `backend/api/routes/engagement_cockpit.py`
  - home summary
  - approvals queue
  - issues queue
  - engagement list/detail
  - sent messages feed
  - draft and issue mutation endpoints
- `backend/services/task_first_engagement_cockpit.py`
  - response view classes for home, approvals, issues, detail, and sent feed
  - `_load_cockpit_data` aggregation layer
  - `_pending_task_for_engagement` prioritization
  - list/detail shaping for visible engagements only
- `backend/services/task_first_engagement_issues.py`
  - issue taxonomy source
  - issue record/action shaping
  - newest-first issue queue
  - rate-limit issue inference and reset estimation
- `backend/services/task_first_engagement_draft_updates.py`
  - replacement-draft request lifecycle used by cockpit edit flows

### Task-first cockpit mutation path

- `backend/services/task_first_engagement_cockpit_mutations.py`
  - `approve_cockpit_draft`
  - `reject_cockpit_draft`
  - `queue_cockpit_draft_update`
  - `act_on_cockpit_issue`
  - `get_cockpit_rate_limit_detail`
  - `get_cockpit_quiet_hours`
  - `update_cockpit_quiet_hours`
  - issue-specific helpers for resume, retry, target approval, and permissions

### Queue boundary

- `backend/queue/payloads.py`
  - `CommunityJoinPayload`
  - `EngagementTargetResolvePayload`
  - `EngagementDetectPayload`
  - `EngagementSendPayload`
  - `AccountHealthRefreshPayload`
- `backend/queue/client.py`
  - `enqueue_community_join`
  - `enqueue_engagement_target_resolve`
  - `enqueue_engagement_detect`
  - `enqueue_manual_engagement_detect`
  - `enqueue_engagement_send`
  - `enqueue_account_health_refresh`
  - deterministic job-id helpers for collection/send/health-refresh

## Compat

### Community-scoped route shards

- `backend/api/routes/engagement_targets.py`
  - operator capabilities, target CRUD, resolve/join/collect/detect jobs
- `backend/api/routes/engagement_settings_topics.py`
  - community settings, topic CRUD, topic examples, older join/detect entry
    points
- `backend/api/routes/engagement_prompts_style.py`
  - prompt-profile CRUD, preview, versions, activation, rollback, style-rule
    CRUD
- `backend/api/routes/engagement_candidates_actions.py`
  - candidate queues, revisions, actions, rollout summary, approve/edit/reject,
    retry/send

### Community-scoped services

- `backend/services/community_engagement.py`
  - pure export facade for older service imports
- `backend/services/community_engagement_views.py`
  - shared view and error types for compat services
- `backend/services/community_engagement_settings.py`
  - community-level mode/posting/account settings plus membership state
- `backend/services/community_engagement_targets.py`
  - target creation, normalization, status, permission, resolve bridge
- `backend/services/community_engagement_topics.py`
  - topic CRUD, examples, keyword normalization and validation
- `backend/services/community_engagement_prompts.py`
  - prompt-profile CRUD, preview rendering, version history, safe template
    validation
- `backend/services/community_engagement_style_rules.py`
  - scope-aware style-rule CRUD and bundle selection
- `backend/services/community_engagement_candidates.py`
  - candidate creation, review actions, duplicate detection, expiry, revisions
- `backend/services/community_engagement_actions.py`
  - action history and semantic-rollout summaries

## Shared support modules

- `backend/services/engagement_candidate_timing.py`
  - reply/review deadlines and timeliness normalization
- `backend/services/engagement_embeddings.py`
  - semantic trigger embeddings and cache
- `backend/services/engagement_opportunity_cadence.py`
  - root vs continuation opportunity classification
- `backend/services/engagement_account_behavior.py`
  - send/read cadence constants and jitter helpers
- `backend/services/engagement_due_state.py`
  - Redis-backed due-state scheduling for collection and read receipts

## Contract notes

- Active backend contract source is task-first plus cockpit route/service files.
- Compat backend files still carry live behavior and data dependencies, but not
  the preferred operator-facing contract.
- `backend/api/routes/engagement.py` is a router/facade, not the best place to
  infer behavior.
