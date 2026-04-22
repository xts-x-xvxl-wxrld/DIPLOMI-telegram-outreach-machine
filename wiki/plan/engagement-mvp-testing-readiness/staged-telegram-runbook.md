# Staged Telegram Engagement Runbook

## Purpose

Run one controlled MVP engagement test without automatic posting. The test proves that an approved
public target can be collected, detected, reviewed, edited, sent as one public reply, and audited.

Do not use this runbook for DMs, auto-send, bulk posting, bulk joining, private groups, or scraping
private member identity.

## Roles

- Operator: owns target approval, bot review, reply approval, and abort decisions.
- Engagement account: dedicated Telegram account with `telegram_accounts.account_pool = 'engagement'`.
- Backend worker stack: API, worker, scheduler, Redis, Postgres, and bot services.

## Phase 0: Local Fake-Adapter Gate

Run these before touching Telegram:

```powershell
python -m pytest -q tests/test_collection_worker.py tests/test_engagement_detect_worker.py tests/test_engagement_send_worker.py tests/test_collection_queue_payloads.py tests/test_engagement_operator_controls.py
python scripts/check_fragmentation.py
```

Expected evidence:

- collection tests show exact `engagement_messages` batches in `collection_runs.analysis_input`.
- detection tests show `collection_run_id` payloads create bounded reply opportunities.
- send tests show stale deadlines, approval, membership, rate-limit, and reply-only checks fail
  closed.
- bot/operator tests show target collection, collection-run status, review, edit, approve, send, and
  audit controls remain reachable.

Stop if any gate fails.

## Phase 1: Preflight

Check the dedicated account:

```sql
select id, phone_label, account_pool, status
from telegram_accounts
where account_pool = 'engagement';
```

Expected evidence: the join/send account is in the `engagement` pool and is healthy. Do not use a
search, personal, or unknown-pool account for joins or sends.

Check the target:

```sql
select id, community_id, approval_status, allow_join, allow_detect, allow_post
from engagement_targets
where id = '<target_id>';
```

Expected evidence:

- `approval_status = 'approved'`.
- controlled dry run: only the permissions needed for the phase are true.
- observe-only real-community run: `allow_join = true`, `allow_detect = true`, `allow_post = false`.
- reply-only send run: `allow_post = true` only for the one approved reply test.

Check engagement settings:

```sql
select community_id, mode, reply_only, require_approval, max_posts_per_day,
       min_minutes_between_posts, quiet_hours_start, quiet_hours_end, assigned_account_id
from engagement_settings
where community_id = '<community_id>';
```

Expected evidence:

- `mode` is `observe`, `suggest`, or `require_approval`; use `require_approval` for the send test.
- `reply_only = true`.
- `require_approval = true`.
- `max_posts_per_day <= 1`.
- `min_minutes_between_posts >= 240`.
- quiet hours are conservative for the target community.
- `assigned_account_id` points to the engagement-pool account.

Check detection configuration:

- OpenAI API key and selected model are present in the API/worker environment.
- prompt profile and style rules are configured for the target topic.
- raw message storage remains off unless the operator explicitly enables it for diagnosis.

## Phase 2: Controlled Group Dry Run

Use a small public or controlled Telegram group where the operator can post a test source message.

1. In the bot, open the target card and confirm readiness.
2. Queue join from the bot with `/join_community <community_id>` or the target-card join control.
3. Confirm membership evidence in the target card or database.
4. Post one realistic public source message in the group.
5. Queue collection with `/target_collect <target_id>`.
6. Inspect `/target_collection_runs <target_id>`.
7. Queue manual detection from the bot if detection did not run automatically after collection.
8. Open reply opportunities with `/engagement_opportunities`.
9. Edit the suggested reply if needed.
10. Approve and send exactly one reply.
11. Inspect `/engagement_actions` or the action audit view.

Expected evidence:

- collection run status is completed and message count is greater than zero.
- `collection_runs.analysis_input.engagement_messages` contains the exact new-message batch.
- the detection job references the same `collection_run_id`.
- the reply opportunity source message ID matches the controlled group source post.
- approval records the operator.
- send creates one `engagement_actions` row with exact outbound text, reply target message ID,
  sent status or fail-closed error, and Telegram sent message ID when successful.

## Phase 3: Real Approved Community Observe-Only

Use one approved public community where the engagement account is allowed to join and observe.

1. Set target permissions to `allow_join = true`, `allow_detect = true`, `allow_post = false`.
2. Confirm settings still require approval and reply-only mode.
3. Join with the engagement account.
4. Let the active collection scheduler run, or manually run `/target_collect <target_id>`.
5. Inspect collection-run status and detection results.
6. Review any reply opportunities without approving sends.

Expected evidence:

- no outbound action rows with `status = 'sent'`.
- collection and detection audit trails exist.
- reply opportunities, if created, are reviewed only as suggestions.
- stale or low-fit opportunities are rejected or expired rather than sent.

## Phase 4: One Approved Reply-Only Send

Proceed only after the observe-only run looks correct.

1. Temporarily enable `allow_post = true` for the single target.
2. Confirm `mode = 'require_approval'`, `reply_only = true`, and `require_approval = true`.
3. Review the source excerpt and final reply in the bot.
4. Approve one reply opportunity.
5. Send from the bot.
6. Immediately return `allow_post` to false unless another single test is explicitly planned.

Expected evidence:

- exactly one send job is queued for the approved reply opportunity.
- send preflight confirms approval, joined membership, target permission, reply deadline, quiet
  hours, and rate limits.
- action audit stores exact outbound text and Telegram reply metadata.
- no DM, broadcast, or second send is created.

## Abort Switches

Use the smallest switch that stops the unsafe path:

- disable the community: set engagement settings `mode = 'disabled'`.
- stop new collection: pause the scheduler service or set collection/detection target permissions
  to false.
- stop sending: set target `allow_post = false` and keep `reply_only = true`.
- clear review queue: reject or expire pending reply opportunities from the bot.
- stop workers: pause worker/scheduler containers if jobs are already queued and the operator needs
  a hard operational stop.

After any abort, inspect pending jobs and action rows before resuming.

## Completion Criteria

The staged test is complete when the operator can point to:

- a dedicated engagement account joined to the approved target.
- one completed collection run with exact public-message batch evidence.
- one detection job tied to that collection run.
- one reviewed reply opportunity with operator approval or rejection evidence.
- for the send phase, one public reply action audit row explaining the final result.
- no evidence of DMs, auto-send, bulk posting, private-surface collection, or person-level scoring.
