# Engagement Cockpit Scheduler State Mismatch

## Summary

Staging shows a task-first engagement for `@tgoutreachtest` in `My engagements`,
but the engagement scheduler reports `targets_checked: 0`. That means the
operator cockpit can surface an engagement that the runtime scheduler does not
see as a runnable engagement target.

## Observed Evidence

- Staging is on commit `7e8cc84` with the manual-collection detect fix deployed.
- The operator-visible engagement detail for the test case shows:
  - target `@tgoutreachtest`
  - topic `Картошка`
  - account `+38671210775`
  - sending mode `Draft`
- The engagement detail API was hit for engagement
  `2cc000d3-a788-4c09-a6bd-5207dd21f785`.
- Staging scheduler logs continue to report:
  - `targets_checked: 0`
  - `jobs_enqueued: 0`
- Worker logs after deploy show startup only, with no collection/read-ack job
  for the test group.

## Why This Matters

The unread test-group message is currently explained by the scheduler seeing no
engagement targets at all. No collection job means no read acknowledgement and
no follow-up detect path, regardless of the already-fixed manual collection
enqueue bug.

## Relevant Code Paths

- Cockpit list visibility:
  - `backend/services/task_first_engagement_cockpit.py`
  - `_visible_engagements()` shows only `active` and `paused` engagements.
- Cockpit detail loading:
  - `backend/services/task_first_engagement_cockpit.py`
  - `get_cockpit_engagement_detail()` loads any engagement row by ID.
- Scheduler seed path:
  - `backend/workers/engagement_scheduler.py`
  - `_load_effective_settings_community_ids()` starts from:
    - `community_engagement_settings.community_id`
    - active `engagements.community_id` joined through `engagement_settings`

## Likely Fault Line

If the operator reached this record from `My engagements`, then the engagement
is probably `active` or `paused` in the cockpit path. The scheduler still
seeing `targets_checked: 0` points to a task-first state sync bug such as:

- active engagement exists, but the required `engagement_settings` join path is
  missing or broken
- active engagement exists, but `engagement.community_id` is null or wrong
- cockpit/runtime paths are reading different readiness truth for the same
  engagement

## Next Checks

1. Inspect engagement `2cc000d3-a788-4c09-a6bd-5207dd21f785` in staging DB:
   - `engagements.status`
   - `engagements.community_id`
   - matching `engagement_settings` row
2. Inspect the linked target/community rows:
   - approved target exists for the same community
   - `allow_detect = true`
3. Compare the cockpit read model and scheduler seed query on that exact
   engagement to find the first place they diverge.

## Expected Fix Shape

Align the scheduler seed path with the task-first cockpit/runtime truth so an
engagement visible in `My engagements` is also eligible for scheduled
collection/detect when its target and settings allow it.
