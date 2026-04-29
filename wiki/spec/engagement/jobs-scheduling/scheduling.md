# Engagement Scheduling Contract

Detailed monitoring and send timing contracts for engagement workflows.

## Scheduling

Engagement detection should run after collection for timely communities and can also run on a
separate low-frequency scheduler tick as a fallback sweep.

### Monitoring Model

Monitoring is a two-stage process:

```text
collection watches approved communities
  -> collection writes an exact new-message engagement batch
  -> engagement.detect is queued with collection_run_id when engagement is enabled
  -> engagement scheduler also checks eligible communities as a fallback sweep
  -> engagement.detect finds fresh post-join trigger messages
  -> engagement.detect drafts from the selected trigger and community context
  -> reply opportunities wait for operator review
  -> fresh reply opportunities notify the operator
```

Collection owns Telegram reads and durable message artifacts. Detection owns engagement decisions.
The engagement scheduler does not directly scrape Telegram in the MVP. It reads durable collection
artifacts or opt-in stored messages. This keeps outbound behavior separate from collection and
prevents the engagement module from becoming an always-on raw chat listener.

Eligibility for a scheduled detection run:

- The community has engagement settings in `observe`, `suggest`, or `require_approval` mode.
- An approved engagement target grants `allow_detect`.
- A completed collection run exists inside the configured detection window.
- For collection-triggered detection, the completed collection run provides `engagement_messages` or
  stored `messages` rows for the new-message batch.
- There is no active reply opportunity already waiting for the same community review flow.
- The current time is outside configured quiet hours.

Opportunity detection should be precise before invoking the drafting model. The first-pass selector
should use the embedding-based semantic matching contract in
`wiki/spec/engagement-embedding-matching.md`, after deterministic eligibility and safety gates such
as:

- negative keyword exclusions
- message age
- whether the message was posted after the engagement account joined
- whether the message is a replyable group message
- dedupe against active reply opportunities and recent sent actions

Semantic matches are trigger opportunities, not send decisions. A match should identify a source
post for review, then the drafting model decides whether the moment is strong enough to create a
reply opportunity. Keyword or phrase matching may remain as a fallback during rollout, but it should
not be the long-term primary selector.

Messages posted before the engagement account joined the community must not trigger new engagement
reply opportunities. They may inform a community-level summary, but the bot should not join a group and
reply to old pre-join discussions as if it had been organically present.

Freshness SLO:

- For engagement-enabled communities with fresh collection artifacts, a qualifying source post
  should produce a committed reply opportunity and operator notification within 10 minutes of
  collection completion.
- The SLO begins when collection has produced a usable sample; collection latency is measured
  separately.
- If the detector misses the SLO, it may still create the opportunity while the source post is before
  `reply_deadline_at`, but the opportunity should be labeled `aging`.
- After `reply_deadline_at`, scheduled detection must skip creating a sendable reply opportunity.

Target response timing:

- Prefer opportunities where the trigger message is 15 to 60 minutes old.
- Skip or downgrade messages younger than 15 minutes unless the operator manually forces detection;
  this avoids instant bot-like replies.
- Skip scheduled draft creation for trigger messages older than 60 minutes by default.
- Manual detection may inspect a wider window for diagnosis, but send preflight should still treat
  stale reply opportunities conservatively.

Default cadence:

| Setting | Default | Meaning |
|---|---:|---|
| `ENGAGEMENT_COLLECTION_DETECT_ON_COMPLETE` | true | queue detection after successful collection for engagement-enabled communities |
| `ENGAGEMENT_ACTIVE_COLLECTION_INTERVAL_SECONDS` | 180 | target compact collection cadence for engagement-enabled communities |
| `ENGAGEMENT_SCHEDULER_INTERVAL_SECONDS` | 3600 | fallback scheduler wakes roughly once per hour |
| `ENGAGEMENT_DETECTION_WINDOW_MINUTES` | 60 | detection considers the latest hour of collected samples |
| `ENGAGEMENT_REPLY_DEADLINE_MINUTES` | 90 | send preflight rejects replies after this source-post age |
| `max_posts_per_day` | 1 | maximum sent replies per community and account in a rolling 24-hour window |
| `min_minutes_between_posts` | 240 | minimum spacing between sent replies for both community and account |

The Docker Compose `scheduler` service runs one `backend.workers.engagement_scheduler` process that
owns both loops: the active collection tick uses `ENGAGEMENT_ACTIVE_COLLECTION_INTERVAL_SECONDS`,
and the fallback detection tick uses `ENGAGEMENT_SCHEDULER_INTERVAL_SECONDS`.

Manual detection can be operator-triggered for an approved target and may use a custom
`window_minutes`, but it still uses the same target permission, topic, prompt, privacy, and
reply opportunity creation rules.

### Send Timing Model

Sending is intentionally separated from monitoring. Detection may create reply opportunities, but it
must not queue `engagement.send` in the MVP.

A public reply may be sent only when all of these are true:

- The reply opportunity is still before `reply_deadline_at` and has status `approved`.
- The approved `final_reply` passes safety and length validation.
- The community settings still allow posting and require approval.
- The engagement target grants `allow_post`.
- The selected engagement account is already joined to the community.
- Reply-only mode can be satisfied by replying to a source Telegram message.
- Quiet hours, rolling daily limits, and minimum spacing checks pass.

Timing behavior should feel sparse and human-supervised:

- Draft quickly enough that the operator can review while the discussion is still current.
- Expire stale reply opportunities rather than sending late replies into a cooled-off thread.
- Use rate limits as hard caps, not goals. The best day may still have zero sends.
- Never batch multiple sends into the same community just because multiple topics matched.
- Treat failed or skipped send attempts as audit events, not reasons to retry aggressively.

Recommended MVP:

- Only run detection for communities with engagement settings enabled.
- Queue detection after fresh collection completion for engagement-enabled communities, including
  the completed `collection_run_id`.
- Keep hourly detection as a fallback sweep, not the primary timely path.
- Skip if there is already an active reply opportunity for the same community/topic/source.
- Skip during quiet hours if configured.
- Do not enqueue sends automatically in MVP.

Scheduler contract:

- Job ID for detection: `engagement.detect:{community_id}:{yyyyMMddHH}`.
- Collection-triggered job ID for detection: `engagement.detect:{community_id}:{collection_run_id}`.
- Job ID for active engagement collection: `collection:engagement:{community_id}:{yyyyMMddHHmm}`.
- Scheduler reads only settings where `mode IN ('observe', 'suggest', 'require_approval')`.
- The collection scheduler skips communities without approved `allow_detect`, with recent successful
  engagement collection, with active collection work, or inside configured quiet hours.
- Scheduler skips communities without a completed collection run in the last configured window.
- Scheduler does not create direct send jobs.
- Manual detection uses a distinct job ID prefix so the operator can force a run.
