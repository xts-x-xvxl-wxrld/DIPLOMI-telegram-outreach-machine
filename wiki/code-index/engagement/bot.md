# Engagement Bot Map

## Scope

This shard covers Telegram bot ownership for engagement callbacks, flows, UI,
formatting, and compat/manual controls.

## Read First

- `bot/callback_handlers.py`
- `bot/engagement_wizard_flow.py`
- `bot/engagement_approval_flow.py`
- `bot/engagement_issue_flow.py`
- `bot/engagement_detail_flow.py`
- `bot/ui_engagement_home.py`
- `bot/ui_engagement_detail.py`
- `bot/formatting_engagement_home.py`
- `bot/formatting_engagement_detail.py`

## Active

### Callback ingress

- `bot/callback_handlers.py`
  - top-level callback router
  - dispatches active operator cockpit actions such as home, approvals, issues,
    detail, sent feed, and wizard re-entry
- `bot/engagement_commands_daily.py`
  - `/engagement` entry command and cancel-edit support
- `bot/engagement_commands_wizard.py`
  - explicit add-engagement command entrypoint

### Home and navigation

- `bot/ui_engagement_home.py`
  - `Engagements` home buttons and per-state action ordering
- `bot/formatting_engagement_home.py`
  - home summary copy and pending-work text

### Wizard flow

- `bot/engagement_wizard_flow.py`
  - five-step target/topic/account/mode/review flow
  - edit re-entry support
  - retry, cancel, and resume-after-topic-create handling
- `bot/formatting_engagement_wizard.py`
  - wizard step copy
- `bot/engagement_wizard_target_flow.py`
  - target resolution helpers used during wizard setup
- `bot/engagement_wizard_join.py`
  - join-status helpers around wizard completion

### Approval flow

- `bot/engagement_approval_flow.py`
  - global/scoped approval queues
  - approve/reject confirmation
  - draft edit request capture
  - placeholder handling for updating drafts
- `bot/formatting_engagement_approval.py`
  - queue headers, draft cards, confirm prompts, result copy

### Issue flow

- `bot/engagement_issue_flow.py`
  - global/scoped issue queues
  - skip tracking
  - issue-action dispatch
  - rate-limit detail and quiet-hours edit subflows
- `bot/formatting_engagement_issue.py`
  - issue queue, issue card, rate-limit detail, quiet-hours formatting

### Engagement detail and sent feed

- `bot/engagement_detail_flow.py`
  - `My engagements`, engagement preview/detail, resume pending task, sent
    messages feed
- `bot/ui_engagement_detail.py`
  - list/detail/feed inline buttons
- `bot/formatting_engagement_detail.py`
  - list rows, engagement detail card, sent-feed rows

## Compat

### Older engagement export surface

- `bot/engagement_handlers.py`
  - export-only facade that re-assembles command and flow modules still used by
    compat imports

### Callback-driven manual/admin controls that remain live

- `bot/engagement_manual_controls.py`
  - per-community settings view/update
  - account assignment confirmation
  - manual join/detect triggers
  - action-history view hook

### Older admin/config/topic/prompt flows

- `bot/engagement_commands_admin.py`
  - target-admin slash-command entrypoints
- `bot/engagement_commands_config.py`
  - prompt/style/topic slash-command entrypoints
- `bot/engagement_targets_flow.py`
  - inline target admin, approvals, permissions, resolve/join/collect/detect
- `bot/engagement_topics_flow.py`
  - topic list/detail/toggle, keyword updates, example removal
- `bot/engagement_prompts_flow.py`
  - prompt list/detail/preview/versions plus style-rule toggles
- `bot/callback_handlers_engagement.py`
  - compat topic-edit callback shard routed through older topic controls

### Topic-brief helpers

- `bot/runtime_topic_brief.py`
  - topic-create/question flow bootstrap
- `bot/runtime_topic_brief_flow.py`
  - question-by-question topic brief builder and preview helpers
- `bot/runtime_topic_brief_style.py`
  - style-rule targeting for topic brief creation
- `bot/ui_engagement_topics.py`
  - topic/detail/topic-brief step markups

### Shared compat formatting and markup

- `bot/ui_engagement.py`
  - older engagement admin/target/settings/topic/prompt/action markups
- `bot/formatting_engagement.py`
  - older admin/settings/topic/prompt/target/action formatting
- `bot/formatting_engagement_review.py`
  - older candidate/action/rollout review formatting

## Boundary notes

- Active operator contract lives in the task-first callback flows, not in the
  older slash-command surfaces.
- Compat bot modules still matter because they own target admin, prompt/style,
  topic authoring, and manual control paths that the backend still exposes.
- When bot behavior and older wiki text disagree, callback handlers plus bot
  tests win.
