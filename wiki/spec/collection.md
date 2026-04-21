# Collection Spec

## Purpose

Collection gathers recent public Telegram messages from operator-approved engagement communities.

The collection worker fetches message data, writes durable collection artifacts, and stops. It does
not decide whether a message is an engagement opportunity.

Discovery-side metadata/member reads are now called **community snapshots** and are handled by
`community.snapshot`. Collection is reserved for engagement message intake.

## Inputs

`collection.run` receives:

```json
{
  "community_id": "uuid",
  "reason": "engagement|manual",
  "requested_by": "telegram_user_id_or_operator|null",
  "window_days": 90
}
```

Manual collection may be operator-triggered for an approved engagement target. Scheduled engagement
collection should use `reason = "engagement"`.

## Responsibilities

- Acquire a Telegram account lease through the account manager.
- Fetch all new visible messages since the last engagement collection checkpoint.
- Update normalized user records when Telegram users are visible.
- Update `community_members` activity counts for the rolling window.
- Write one `community_snapshots` row.
- Write one `collection_runs` row.
- Write compact capped `collection_runs.analysis_input`.
- Write raw `messages` rows only when `communities.store_messages = true`.
- Enqueue `engagement.detect` after successful engagement collection when the community is eligible.

## Non-Responsibilities

- No OpenAI calls.
- No relevance scoring.
- No final topic classification.
- No outreach behavior.
- No engagement opportunity detection.
- No reply drafting.
- No operator notification.
- No business logic beyond collection persistence and capped artifact preparation.

## Default Raw Message Policy

Raw message storage is opt-in.

Community snapshots do not fetch messages. They write community metadata, visible members, and a
completed run with analysis skipped through the `community.snapshot` path.

When `communities.store_messages = false`:

- messages are fetched in memory
- activity counts, checkpoint metadata, and compact collection artifacts are persisted
- raw messages are discarded
- no `messages` rows are written

When `communities.store_messages = true`:

- the same aggregation path runs
- raw message rows are also written to `messages`

## Engagement Collection Mode

Engagement collection mode is used only for communities that have been explicitly approved for
engagement detection. Its job is to make recent discussion available to the detection worker quickly
and exactly.

Eligibility:

- The community has `community_engagement_settings.mode IN ('observe', 'suggest', 'require_approval')`.
- An approved `engagement_targets` row grants `allow_detect = true`.
- The community is accessible through the account selected for collection.
- The current time is outside configured engagement quiet hours when collection is being run only for
  engagement.

Collection behavior:

- Pull all new visible messages since the last successful engagement collection checkpoint.
- Do not re-fetch full history on normal scheduled runs.
- Use a checkpoint based on the highest collected Telegram message ID and, where useful, the latest
  message timestamp.
- Keep overlap small but nonzero when possible so transient ordering issues do not drop messages;
  dedupe by `(community_id, tg_message_id)`.
- Record the checkpoint range on the `collection_runs` row so detection can explain which batch it
  inspected.
- Treat empty new-message batches as successful collection runs with `messages_seen = 0`.
- Continue to update snapshots and activity counts when those paths are enabled.

Recommended checkpoint fields, whether stored directly on `collection_runs` or inside a compact
artifact:

```json
{
  "engagement_checkpoint": {
    "from_tg_message_id_exclusive": 1230,
    "through_tg_message_id_inclusive": 1245,
    "from_message_date_exclusive": "iso_datetime|null",
    "through_message_date_inclusive": "iso_datetime|null"
  }
}
```

Engagement detection batch:

Detection needs exact source-message records, not only a sampled analysis summary. The collection
run should therefore expose an engagement batch with every new collected message needed for
detection. It may be backed by raw `messages` rows, by a short-retention collection artifact, or by
both.

```json
{
  "engagement_messages": [
    {
      "tg_message_id": 1245,
      "text": "message text",
      "message_date": "iso_datetime",
      "reply_to_tg_message_id": 1244,
      "reply_context": "parent message text or null",
      "is_replyable": true,
      "message_type": "text"
    }
  ]
}
```

Batch rules:

- Include every new text-bearing message that detection may inspect.
- Include message IDs and timestamps for every detection-eligible message.
- Include reply target IDs and parent text when available.
- Mark channel posts, system messages, deleted messages, or other non-replyable items as
  `is_replyable = false`.
- Keep media-only messages out of detection unless they have useful captions.
- Do not call OpenAI or topic-matching code in collection.
- Do not create engagement rows from collection.
- Do not notify the operator from collection.

After a successful engagement collection run:

1. Commit the collected messages, snapshot, `collection_runs` row, and checkpoint.
2. If the batch contains new messages and detection is allowed, enqueue `engagement.detect`.
3. Pass only `community_id`, `collection_run_id`, and timing/window metadata in the queue payload.
4. Let `engagement.detect` load the batch and decide whether any reply opportunity exists.

Default cadence for engagement collection should be shorter than analysis collection. The current
target is every 10 minutes for engagement-enabled communities, with the engagement scheduler acting
as a fallback rather than the primary trigger.

## Collection Artifact

The compact collection artifact may live on `collection_runs.analysis_input` until a dedicated
engagement-batch table exists. It must follow the queue spec envelope.

Rules:

- no full message history
- no phone numbers
- no person-level scores
- no unnecessary Telegram user identity
- maximum 100 message examples
- maximum 500 characters per message example
- recommended maximum serialized size: 256 KB

## Inaccessible Communities

If a monitored community becomes inaccessible:

- record the collection failure or dropped state clearly
- treat it as a community access issue, not an account-health issue
- do not mark the Telegram account unhealthy unless the error is account-level

## Safety Rules

- No business logic in collection.
- Phone numbers are never collected.
- Person-level scoring is forbidden.
- OpenAI calls happen only in analysis, not collection.
