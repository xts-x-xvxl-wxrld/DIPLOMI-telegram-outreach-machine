# Engagement Code Map

Code-first engagement map used to classify the current repo before pruning or
rewriting wiki contracts.

## Purpose

This map covers the full engagement picture, not only the newest task-first
surface.

Every area should be read as one of:

- `active` - current operator-facing or worker-facing path
- `compat` - still present for migration or compatibility
- `stale` - no longer trustworthy as a contract source

## Read First

- `backend/api/routes/engagement.py`
- `backend/api/routes/engagement_task_first.py`
- `backend/api/routes/engagement_cockpit.py`
- `backend/services/task_first_engagements.py`
- `backend/services/task_first_engagement_cockpit.py`
- `backend/services/task_first_engagement_cockpit_mutations.py`
- `backend/services/task_first_engagement_issues.py`
- `backend/db/models_engagement.py`
- `backend/queue/payloads.py`
- `backend/queue/client.py`
- `bot/callback_handlers.py`
- `bot/engagement_wizard_flow.py`
- `bot/engagement_approval_flow.py`
- `bot/engagement_issue_flow.py`
- `bot/engagement_detail_flow.py`

## Unified Picture

### Active

These are the current contract-bearing engagement surfaces.

#### Task-first write path

- `backend/api/routes/engagement_task_first.py`
  - first-class engagement create, patch, settings, confirm, retry
- `backend/services/task_first_engagements.py`
  - draft reuse, wizard field writes, confirm/retry semantics, join/detect
    enqueue points
- `backend/api/schemas.py`
  - task-first request and response DTOs

#### Task-first cockpit read and mutation path

- `backend/api/routes/engagement_cockpit.py`
  - home, approvals, issues, engagement list/detail, sent feed, issue subflows
- `backend/services/task_first_engagement_cockpit.py`
  - home/list/detail/read models and pending-task selection
- `backend/services/task_first_engagement_cockpit_mutations.py`
  - draft approve/reject/edit, issue actions, rate-limit, quiet-hours, resume
- `backend/services/task_first_engagement_issues.py`
  - issue taxonomy and issue queue generation
- `backend/services/task_first_engagement_draft_updates.py`
  - replacement-draft request lifecycle

#### Bot path for active engagement UX

- `bot/callback_handlers.py`
  - main engagement callback dispatch
- `bot/ui_common.py`
  - callback constants and callback-family grammar
- `bot/ui_engagement_home.py`
  - `Engagements` home buttons
- `bot/engagement_wizard_flow.py`
  - add/edit wizard control flow
- `bot/engagement_approval_flow.py`
  - approval queue and review actions
- `bot/engagement_issue_flow.py`
  - issue queue and issue-fix flows
- `bot/engagement_detail_flow.py`
  - `My engagements`, detail, sent feed, pending-task resume

#### DB and migration truth for the active model

- `backend/db/models_engagement.py`
  - engagement tables and invariants
- `alembic/versions/20260428_0013_task_first_engagements.py`
- `alembic/versions/20260428_0014_engagement_draft_update_requests.py`
- `alembic/versions/20260428_0015_engagement_target_duplicates.py`
- `alembic/versions/20260430_0016_engagement_opportunity_cadence.py`

#### Queue and worker seams

- `backend/queue/payloads.py`
  - payload DTOs and job-shape helpers
- `backend/queue/client.py`
  - enqueue entrypoints and deterministic job IDs
- `backend/workers/community_join.py`
- `backend/workers/engagement_detect.py`
- `backend/workers/engagement_scheduler.py`
- `backend/workers/engagement_send.py`

#### Active test anchors

- `tests/test_engagement_api.py`
- `tests/test_engagement_task_first_wizard_api.py`
- `tests/test_engagement_schema.py`
- `tests/test_task_first_engagement_migration.py`
- `tests/test_bot_engagement_wizard.py`
- `tests/test_bot_engagement_cockpit_home.py`
- `tests/test_bot_engagement_issue_handlers.py`
- `tests/test_bot_engagement_detail_handlers.py`

### Compat

These paths are still part of the repo and the combined router, but they should
not be treated as the primary contract source for the engagement-first cleanup.

#### Combined router and mixed surface

- `backend/api/routes/engagement.py`
  - umbrella router that still exposes both task-first and older engagement
    surfaces side by side

#### Community-scoped settings and topic/admin paths

- `backend/api/routes/engagement_settings_topics.py`
- `backend/api/routes/engagement_targets.py`
- `backend/api/routes/engagement_prompts_style.py`
- `backend/api/routes/engagement_candidates_actions.py`
- `backend/services/community_engagement_settings.py`
- `backend/services/community_engagement_targets.py`
- `backend/services/community_engagement_topics.py`
- `backend/services/community_engagement_prompts.py`
- `backend/services/community_engagement_style_rules.py`
- `backend/services/community_engagement_candidates.py`
- `backend/services/community_engagement_actions.py`
- `backend/services/community_engagement_views.py`

These still matter because active task-first behavior can adapt to or coexist
with older engagement data and admin flows.

### Stale Or Suspect

These should not be used as contract sources without fresh code verification.

- broad engagement verification plans under `wiki/plan/engagement-cockpit-verification/`
- older engagement control specs under `wiki/spec/bot-engagement-controls/`
- older cockpit direction docs such as `wiki/spec/bot-operator-cockpit*.md`
- semantic rollout surfaces referenced from older engagement candidate/action
  docs, unless current code/tests still require them

## Boundaries

Use this split while cleaning up:

- API contract source: task-first and cockpit route files plus schemas/tests
- Bot contract source: callback handlers, UI callback builders, and handler
  tests
- Queue contract source: queue payload/client files and worker tests
- DB contract source: engagement models plus Alembic revisions and schema tests
- Legacy reference only: older community-scoped engagement and admin docs

## Next Use

Use this map to drive the next pass:

1. classify engagement wiki files against these code surfaces
2. mark each doc as keep, rewrite, compat-only, or historical
3. remove noise only after every doc has a place in the code map
