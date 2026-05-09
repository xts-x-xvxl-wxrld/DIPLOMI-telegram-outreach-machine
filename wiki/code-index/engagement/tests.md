# Engagement Test Map

## Scope

This shard groups the engagement test suite by functionality so code changes can
find the right anchors quickly.

## API and schema

- `tests/test_engagement_api.py`
  - combined engagement route coverage, auth, target/settings/topic/prompt/
    candidate/action endpoints
- `tests/test_engagement_cockpit_draft_edit_api.py`
  - focused cockpit draft-edit enqueue and queue-failure coverage for the rewrite path
- `tests/test_engagement_task_first_wizard_api.py`
  - task-first wizard create/patch/settings/confirm path
- `tests/test_engagement_api_candidates.py`
  - candidate API read/review behaviors
- `tests/test_engagement_api_create_duplicates.py`
  - duplicate target/create handling
- `tests/test_engagement_schema.py`
  - enum/default/constraint/index/DDL checks
- `tests/test_task_first_engagement_migration.py`
  - task-first backfill migration regression

## Backend services and workers

- `tests/test_engagement_targets.py`
  - target normalization, resolve, permission rules
- `tests/test_engagement_detect_worker.py`
  - detect orchestration, sampling, duplicate suppression, model decision flow
- `tests/test_engagement_detect_candidate_creation.py`
  - root-vs-continuation candidate creation and continuation prompt/runtime
    contract coverage
- `tests/test_engagement_detect_draft_updates.py`
  - targeted rewrite-request detect coverage for replacement-draft completion and fail-open recovery
- `tests/test_engagement_detect_samples.py`
  - exact collection-run vs. artifact fallback sample-loading coverage
- `tests/test_engagement_detect_warmup.py`
  - post-join warmup draft creation behavior
- `tests/test_engagement_send_worker.py`
  - send preflight, idempotency, rate-limit and Telethon error mapping
- `tests/test_engagement_scheduler.py`
  - scheduler cadence, skip reasons, quiet-hours handling, due-state behavior
- `tests/test_engagement_account_behavior.py`
  - jitter and account-behavior helpers
- `tests/test_engagement_embeddings.py`
  - embedding cache reuse, vector validation, selector ordering
- `tests/test_engagement_prompt_controls.py`
  - prompt-template variable safety
- `tests/test_telegram_engagement.py`
  - Telethon adapter behavior
- `tests/test_telegram_engagement_adapter.py`
  - adapter-facing seam coverage

## Active task-first bot cockpit

- `tests/test_bot_engagement_cockpit_home.py`
  - home formatting, action ordering, visibility rules, callback routing
- `tests/test_bot_engagement_home_handlers.py`
  - home copy and markup state coverage
- `tests/test_bot_engagement_wizard.py`
  - add/edit wizard flow outside the confirm-only regression shard
- `tests/test_bot_engagement_wizard_confirm.py`
  - wizard confirm success/error handoff coverage
- `tests/test_bot_engagement_approval_handlers.py`
  - approval queue, confirmations, edit request handling
- `tests/test_bot_engagement_approval_ingress.py`
  - free-text approval edit submission plus `/cancel_edit` and `/resume_edit`
    coverage for the split callback/message ingress seam
- `tests/test_bot_engagement_issue_handlers.py`
  - issue queue/actions, skip, quiet-hours editing, rate-limit detail
- `tests/test_bot_engagement_issue_formatting.py`
  - issue card/queue formatting
- `tests/test_bot_engagement_detail_handlers.py`
  - `My engagements`, detail, sent feed, resume action
- `tests/test_bot_engagement_setup_flows.py`
  - setup and topic-brief subflows

## Compat and manual control bot coverage

- `tests/test_bot_engagement_handlers.py`
  - legacy/compat handler routing and shared engagement callbacks
- `tests/test_engagement_operator_controls.py`
  - target admin and manual control callbacks
- `tests/test_bot_engagement_wizard_compat.py`
  - legacy field-name compatibility for wizard edit re-entry
- `tests/test_bot_engagement_topic_create_command.py`
  - topic-create command path
- `tests/test_bot_engagement_wizard_topic_brief.py`
  - topic-brief wizard behavior

## Historical or suspect references

- `tests/test_engagement_semantic_eval_fixtures.py`
  - semantic matching fixture contract only; useful for embeddings/detect work,
    not a primary operator contract source

## Boundary notes

- Bot callback tests are the strongest contract source for operator UX details.
- Worker tests are the strongest contract source for send/detect/scheduler edge
  cases.
- When older compat docs disagree with tests, the tests win.
