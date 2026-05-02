# Contract Surface Rationalization

## Goal

Reduce the engagement/search contract surface to a small maintained set whose
truth comes from active code and tests instead of overlapping wiki history.

## Authority Order

When written contracts disagree, resolve them in this order:

1. active tests
2. API schemas, DB models, and migrations
3. route, worker, bot-client, and handler code
4. spec docs
5. plan and verification docs

Plans and verification notes may describe history, intended rollout, or stale
 gaps. They are not authoritative over shipped code/tests.

## Canonical Contract Set

### Keep And Maintain

These are the written contracts worth keeping as first-class references:

| Surface | Canonical doc | Primary code/test authority |
| --- | --- | --- |
| Task-first engagement API and wizard semantics | `wiki/spec/api/engagement.md` | `backend/api/routes/engagement_task_first.py`, `backend/api/schemas.py`, `tests/test_engagement_api.py` |
| Task-first engagement bot surfaces and callback grammar | `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md` | `bot/ui_common.py`, `bot/ui_engagement_home.py`, `bot/callback_handlers.py`, `bot/engagement_wizard_flow.py`, `tests/test_bot_ui.py`, `tests/test_bot_engagement_wizard.py`, `tests/test_bot_engagement_cockpit_home.py`, `tests/test_bot_engagement_issue_handlers.py` |
| Engagement queue/job payloads and worker handoff | `wiki/spec/queue/job-types/engagement.md` | `backend/queue/payloads.py`, `backend/queue/client.py`, `tests/test_collection_queue_payloads.py`, `tests/test_collection_worker.py`, `tests/test_engagement_send_worker.py`, `tests/test_engagement_scheduler.py` |
| Engagement DB invariants and migration guarantees | `wiki/spec/database/engagement.md` | `backend/db/models_engagement.py`, `alembic/versions/20260428_0013_task_first_engagements.py`, `alembic/versions/20260428_0014_engagement_draft_update_requests.py`, `alembic/versions/20260428_0015_engagement_target_duplicates.py`, `alembic/versions/20260430_0016_engagement_opportunity_cadence.py`, `tests/test_engagement_schema.py`, `tests/test_task_first_engagement_migration.py` |
| Search API and search schema contracts | `wiki/spec/api/briefs-search.md`, `wiki/spec/database/search.md`, `wiki/spec/queue/job-types/brief-discovery-search.md` | `backend/api/routes/search.py`, `backend/api/schemas_search.py`, `backend/db/models_search.py`, `backend/queue/payloads.py`, `backend/queue/client.py`, `tests/test_search_api.py`, `tests/test_search_schema.py` |

### Keep But Demote

These docs may remain, but they should be treated as overview or historical
context instead of authoritative contract sources:

- `wiki/spec/engagement.md`
- `wiki/spec/bot-engagement-controls.md`
- `wiki/spec/bot-operator-cockpit.md`
- `wiki/spec/bot-operator-cockpit-v2.md`
- `wiki/plan/engagement-cockpit-verification.md`

## Rewrite Or Fold Back

These files describe real areas, but their current wording drifts from active
behavior and should be rewritten or folded into the canonical docs above:

- `wiki/spec/bot-engagement-controls/config-editing.md`
  Reason: still carries obsolete MVP statements around automatic sending.
- `wiki/plan/engagement-cockpit-verification/phase-2-code-mapping.md`
  Reason: callback grammar and routing notes drift from current bot surfaces.
- `wiki/plan/engagement-cockpit-verification/phase-3-test-coverage-review.md`
  Reason: wizard mode semantics and fresh-start notes drift from current
  code/tests and mixes audit history with live contract language.

## Contract Boundaries To Remove From Canonical Docs

Do not preserve these as first-class contracts unless product work revives them:

- community-scoped engagement-settings behavior as the primary operator model
- rollout-era semantic-matching review semantics
- speculative verification notes that are not asserted by tests
- broad menu/navigation narratives duplicated across multiple engagement docs

Those can remain as migration or historical notes, but they should not compete
with the task-first contract set.

## Immediate Cleanup Order

1. Normalize externally visible engagement callback and field vocabulary.
   Current example: `mode` should be the wizard field name, not
   `sending_mode`.
2. Correct the canonical docs to match shipped task-first behavior.
3. Mark drift-heavy verification docs as historical or rewrite them as short
   audit notes.
4. Collapse duplicate engagement documentation so bot, API, queue, and DB
   contracts each have one maintained home.
5. Repeat the same reduction for search after engagement is stable.

## Acceptance Criteria

- The repo has one explicit plan that names the canonical contract set.
- The task-first engagement surface uses one external field vocabulary for
  wizard reentry.
- `wiki/index.md` points at this plan.
- The affected spec/log entries reflect the normalization.
