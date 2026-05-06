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

- cockpit includes `paused` engagements in `My engagements`, but the scheduler
  seeds only `active` task-first engagements
- active engagement exists, but the required `engagement_settings` join path is
  missing or broken
- active engagement exists, but `engagement.community_id` is null or wrong
- cockpit/runtime paths are reading different readiness truth for the same
  engagement

## Code Check Result

Static code inspection narrows the fault line further:

- The cockpit visibility predicate explicitly includes both `active` and
  `paused` engagements in `backend/services/task_first_engagement_cockpit.py`.
- The scheduler seed query only includes:
  - `community_engagement_settings.community_id`
  - `engagements.community_id` for task-first engagements that are both
    `active` and joined to `engagement_settings`
- The shared settings resolver also only reads task-first settings from
  `active` engagements, not `paused` ones, before it falls back to legacy
  community settings.

That means a `paused` engagement can be visible in `My engagements` while being
completely invisible to scheduler target loading.

For this exact staging case, the likely causes rank as:

1. `engagements.status = paused` for
   `2cc000d3-a788-4c09-a6bd-5207dd21f785`
2. the row is `active`, but runtime and cockpit are reading different deployed
   state or different database state
3. the row is `active`, but task-first data integrity is broken
   (`engagement_settings` missing/bad join or `engagements.community_id`
   corrupted)

The normal task-first confirm path makes cause 3 less likely than 1 or 2,
because it requires `engagement_settings` and only then flips the engagement to
`active`.

## Staging Check Results

Direct staging DB inspection and local execution of the current scheduler loader
against the staging database changed the diagnosis:

- `engagements.id = 2cc000d3-a788-4c09-a6bd-5207dd21f785` is:
  - `status = active`
  - `community_id = b8dc2e9e-d67c-45ee-bccc-79c7740b3e78`
- A matching `engagement_settings` row exists with:
  - `mode = suggest`
  - `allow_join = true`
  - assigned account set
- The linked target row is:
  - `status = approved`
  - `allow_detect = true`
  - `allow_join = true`
  - `allow_post = false`
- The exact scheduler seed query does include that `community_id`.
- Running the current repo code against staging DB returns:
  - detection targets: 3 total, including `b8dc2e9e-d67c-45ee-bccc-79c7740b3e78`
  - collection targets: 4 total, including `b8dc2e9e-d67c-45ee-bccc-79c7740b3e78`

That falsifies the main task-first data-integrity suspects for this exact
engagement:

- not paused
- not missing `engagement_settings`
- not missing scheduler seed membership
- not missing target detect permission

The issue is now more specifically a runtime-environment mismatch:

- the running staging scheduler process is not behaving like the current repo
  code when pointed at the current staging database
- or the scheduler is connected to different runtime state than the DB checked
  here

## Runtime Proof

The running staging scheduler logs provide a direct stale-code signal:

- live scheduler logs say `Engagement scheduler tick: {...}`
- the current repo no longer contains that log string anywhere
- the current scheduler code logs:
  - `Engagement collection scheduler tick: {...}`
  - `Engagement detection scheduler tick: {...}`

That means the running scheduler container/process is not executing the current
`backend/workers/engagement_scheduler.py` from this checkout.

Given the DB checks above already proved the target is loadable by current code,
the highest-confidence root cause is now:

1. stale scheduler runtime/image still running older code
2. less likely: scheduler runtime pointed at different env/db while also using
   older code

This explains the zero-target scheduler signal, but it does not yet prove that
the unread / not-reading-target-community symptom has only one cause. If that
symptom persists after the scheduler is refreshed, the read/collection path
still needs a separate follow-up investigation.

## Next Checks

1. Inspect engagement `2cc000d3-a788-4c09-a6bd-5207dd21f785` in staging DB:
   - completed: engagement is `active`, has settings, and its `community_id`
     is in the scheduler seed query
2. Inspect the linked target/community rows:
   - completed: target is approved and `allow_detect = true`
3. Distinguish which scheduler log is zero:
   - completed: the observed zero-target log is the detection scheduler
4. Next runtime check:
   - completed enough to identify stale runtime code from the live log string
5. Next fix step:
   - rebuild/restart the staging scheduler so it runs the current image/code,
     then re-check detection and collection scheduler logs
   - if zero-target logs persist after that restart, inspect the scheduler
     container's effective `DATABASE_URL`
   - if zero-target logs are fixed but target communities still are not being
     read, continue with a separate collection/read-path trace

## Test Gap

Current scheduler tests exercise tick behavior with injected target lists, but
do not cover the real DB loader path from task-first confirm -> engagement row
-> scheduler seed query. That leaves this exact mismatch unguarded by tests.

## Expected Fix Shape

Align the scheduler seed path with the task-first cockpit/runtime truth so an
engagement visible in `My engagements` is also eligible for scheduled
collection/detect when its target and settings allow it.
