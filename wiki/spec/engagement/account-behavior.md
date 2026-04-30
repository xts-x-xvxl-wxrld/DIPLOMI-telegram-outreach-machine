# Engagement Account Behavior

Hardcoded account behavior rules for making managed engagement accounts behave like cautious
Telegram participants rather than synchronized bots. These rules are product defaults, not
operator-configurable controls in the first implementation.

## Goals

- Spread account activity across communities so reads and sends are not globally synchronized.
- Keep one account consistently attached to a community unless the account becomes unhealthy.
- Avoid immediate post-join replies.
- Keep send and read behavior simple enough to test and reason about.

## Non-Goals

- No auto-reactions in the first version.
- No skip just because a conversation has newer messages.
- No complex send-delay policy based on activity, sentiment, or message age.
- No business logic in the collection worker beyond adapter-level read acknowledgement hooks.

## Send Behavior

Before sending an approved public reply:

- Verify the source Telegram message is still accessible/replyable.
- Skip the send if the source message was deleted or is no longer replyable.
- Do not skip only because the conversation moved on.
- Apply a simple bounded send delay by scheduling the `engagement.send` job for a future due time,
  using stable jitter so tests can assert the scheduled range.
- Do not sleep inside the send worker to enforce the delay; worker slots should only be occupied
  while doing active preflight, account leasing, Telegram presence, or send work.
- Continue using existing reply deadlines, approval checks, idempotency, and audit rows.

Initial defaults:

```text
send_delay_min_seconds = 45
send_delay_max_seconds = 120
```

Scheduling rules:

- Compute send delay when an approved reply is queued, not when `engagement.send` starts.
- Prefer RQ delayed scheduling through Redis when available.
- Keep the idempotent job ID `engagement.send:{candidate_id}` so repeated approval clicks do not
  create multiple delayed sends.
- Store the intended send time in `engagement_actions.scheduled_at` when the action row exists.
- When the delayed job runs, repeat all final preflight checks before contacting Telegram.
- If RQ delayed scheduling is unavailable in a deployment, use the engagement scheduler loop and
  Redis due-state as the fallback. Worker sleep is only an emergency simplification, not the target
  design.

## Post-Join Acclimation

After an engagement account joins a community:

- Read the latest 3-5 visible messages once.
- Mark that initial batch as read when Telegram allows it.
- Start an acclimation window before detection or sending is allowed.
- During the window, passively read newly arriving messages on jittered intervals.
- Cap warmup read checks so the account does not mark every poll as read.

Initial defaults:

```text
initial_join_read_limit = 5
warmup_duration_minutes = 60
warmup_read_interval_min_minutes = 1
warmup_read_interval_max_minutes = 15
warmup_read_checks_max = 5
```

Detection and sending must ignore communities whose selected engagement membership is still inside
the post-join acclimation window.

## Jittered Community Collection

The scheduler should avoid enqueueing all active engagement communities on the same global cadence.
Keep one scheduler loop, but give each active community its own due time.

Recommended low-complexity state:

```text
engagement:collection:next:{community_id}
```

Rules:

- If a community has no due time, set it to `now + jitter(1-15 minutes)`.
- The scheduler may wake every 60 seconds.
- Enqueue collection only for communities whose due time has passed.
- After enqueue, set the next due time to `now + jitter(3-15 minutes)`.
- Store this scheduling state outside Telegram account session files.

Collection may still keep backend data fresh, but Telegram read acknowledgements must follow their
own jittered account/community rhythm.

## Jittered Read Receipts

For each joined engagement account/community pair:

- Maintain a next read time.
- Mark messages read only when new messages exist and the pair is due.
- Schedule the next read acknowledgement with jitter in the 1-15 minute range.
- Do not mark every collection poll as read.
- Use stable pseudo-random jitter seeded by account, community, and time bucket so behavior is
  spread out but testable.

Recommended low-complexity state:

```text
engagement:read:next:{telegram_account_id}:{community_id}
```

## Account Consistency And Replacement

Selection should prefer the same engagement account for a community:

1. Use the assigned account if it is healthy and in the engagement pool.
2. Else use an existing joined membership for the community if the account is healthy.
3. Else acquire a fresh healthy engagement account and join it.

If the previously selected account is banned, unauthorized, deactivated, or otherwise unhealthy,
the system may replace it with another healthy engagement account. It must not rotate accounts only
for load balancing or stylistic variety.

## Account Health Refresh

Run scheduled account health refresh every 8 hours for all managed Telegram accounts.

Checks:

- Connects to Telegram.
- Session is still authorized.
- `get_me()` succeeds.
- Account is not banned, deactivated, or session-revoked.
- FloodWait state is still respected.
- Optional spot checks may verify access to a small number of joined engagement communities.

Health refresh updates account availability before join, collection, detection, and send workers
select accounts.

Implementation contract:

- The engagement scheduler enqueues `account.health_refresh` roughly every 8 hours.
- The worker skips disabled-pool accounts and accounts with active leases.
- Healthy authorized sessions are marked `available` with cleared `last_error` and
  `flood_wait_until`.
- FloodWait maps to `rate_limited` with `flood_wait_until`.
- Banned, deauthorized, deactivated, invalid auth-key, or revoked sessions map to `banned`.

## Reply Cadence

Hardcoded account-level cadence limits apply to started root opportunities, not every message in a
conversation already started by the managed account.

```text
max_started_opportunities_per_account_4h = 3
max_started_opportunities_per_account_24h = 12
min_minutes_between_started_opportunities = 15
same_community_new_opportunity_cooldown_minutes = 90
max_continuation_replies_per_opportunity_24h = 3
min_minutes_between_continuation_replies = 5
```

Root opportunities count against account caps once they are approved and scheduled, even if the
delayed send has not run yet. This prevents multiple scheduled starts from bypassing sparse-account
behavior.

Same-community cooldown applies to new unrelated root opportunities. It must not block deterministic
continuations where the new source message is a direct reply to the managed account's previous sent
message in that community.

MVP continuation detection is deliberately conservative:

- A reply opportunity is a continuation only when its source Telegram message has
  `reply_to_tg_message_id` pointing at a message previously sent by the selected managed engagement
  account in that community.
- Semantic "same discussion" continuation detection is out of scope for the first version.
- Continuations bypass root-opportunity account caps but still require approval, source-message
  preflight, account health, membership, idempotency, and continuation-specific spacing limits.
- If the system cannot prove a candidate is a direct continuation, classify it as a root
  opportunity.

Recommended durable fields on `engagement_candidates`:

```text
opportunity_kind text NOT NULL DEFAULT 'root'
                  -- root | continuation
root_candidate_id uuid REFERENCES engagement_candidates(id)
source_reply_to_tg_message_id bigint
conversation_key text
```

The first implementation may use service-level inference before adding all fields, but durable
fields are preferred once continuations are operator-visible or counted in cadence checks.

## Implementation Notes

- Prefer Redis keys for collection/read due times before adding schema.
- Keep jitter helpers pure and injectable for tests.
- Preserve current send audit semantics: skipped sends must record clear reasons, while read and
  typing failures remain best-effort presence failures.
- Collection workers may call adapter-level read acknowledgement helpers, but detection and
  candidate creation rules remain outside collection.
