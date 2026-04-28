# Task-First Migration Hotfix Plan

## Goal

Restore staging deploys by fixing the `20260428_0013_task_first_engagements`
backfill query so Postgres can run it during `alembic upgrade head`.

## Scope

- patch the migration to avoid `min(uuid)` on `engagement_candidates.topic_id`
- preserve the single-topic backfill rule for `engagements.topic_id`
- add a regression test that locks the query away from UUID aggregation
- rerun local parity checks, push the fix, and redeploy staging

## Notes

- The deploy checkout is already resetting to the latest `main` commit before
  failing, so no deploy-script changes are needed for this slice.
