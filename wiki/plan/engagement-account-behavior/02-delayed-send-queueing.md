# Slice 2: Delayed Send Queueing

Status: implemented.

## Goal

Delay approved public replies through Redis/RQ scheduling instead of sleeping inside the
`engagement.send` worker.

## Scope

- Extend `backend.queue.client.enqueue_job` with an optional delayed enqueue path.
- Update `enqueue_engagement_send` to accept `scheduled_at` or `delay_seconds`.
- Compute the 45-120 second stable delay when a candidate is approved and queued.
- Preserve the idempotent job ID `engagement.send:{candidate_id}`.
- Verify scheduled-job promotion exists in the Docker/VPS runtime. If not, add a scheduler-loop
  fallback before enabling delayed sends.
- Set `engagement_actions.scheduled_at` when a queued action row exists before the delayed job runs;
  otherwise record the scheduled time in queue metadata and let `engagement.send` create/resume the
  audit row at execution time.

## Code Areas

- `backend/queue/client.py`
- `backend/api/routes/engagement_candidates_actions.py`
- `backend/services/task_first_engagement_cockpit_mutations.py`
- `tests/test_engagement_api.py`
- `tests/test_engagement_send_worker.py`
- Docker/worker startup files if scheduled-job promotion is missing.
- `wiki/spec/queue.md` if the queue contract changes.

## Acceptance

- Approved sends are queued for a future due time.
- Duplicate approval cannot create multiple delayed send jobs.
- `engagement.send` still repeats final preflight when the delayed job runs.
- Queue tests cover immediate enqueue and delayed enqueue paths.
- Runtime documentation or tests prove due scheduled jobs are promoted without relying on worker
  sleep.

## Dependencies

Requires Slice 1 for the delay calculation.
