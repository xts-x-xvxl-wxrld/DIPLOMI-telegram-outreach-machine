# Engagement MVP Collection And Detection Slices

## Slice 1: Engagement Collection Worker

Status: completed.

Tasks:

- Implement `backend/workers/collection.py` or an equivalent worker shard and wire
  `collection.run` dispatch to it.
- Add a fakeable Telegram collection adapter, separate from `telegram_snapshot.py`, that can:
  - resolve the community entity from existing `communities` fields
  - fetch new visible messages since the last successful engagement checkpoint
  - keep a small overlap and dedupe by `(community_id, tg_message_id)`
  - include text messages and media captions, while skipping media-only messages
  - include `reply_to_tg_message_id`, parent `reply_context` when available, message date, and
    `is_replyable`
  - map FloodWait and banned/deauthorized sessions to account-manager outcomes
- Acquire and release a `collection` account lease with `finally`-safe cleanup.
- Persist a completed or failed `collection_runs` row for every attempted run.
- Update `community_snapshots` metadata when available.
- Update `users` and `community_members` activity counts only from visible attributable Telegram
  users, without phone numbers or person-level scores.
- Write raw `messages` rows only when `communities.store_messages = true`.

Acceptance:

- Empty new-message batches complete successfully with `messages_seen = 0`.
- Inaccessible communities produce a failed collection run or clear dropped/access state without
  marking the account unhealthy unless the error is account-level.
- Collection worker tests cover success, empty batch, inaccessible community, FloodWait, banned
  session, `store_messages = false`, and `store_messages = true`.

## Slice 2: Exact Batch And Detection Payload Contract

Status: completed.

Tasks:

- Extend `EngagementDetectPayload` with `collection_run_id: UUID | None`.
- Extend `enqueue_engagement_detect` to accept `collection_run_id`.
- Use job IDs shaped as `engagement.detect:{community_id}:{collection_run_id}` for
  collection-triggered detection and keep hourly/manual IDs for fallback/manual runs.
- After a successful engagement collection commit, enqueue `engagement.detect` only when:
  - the batch contains at least one new text-bearing detection-eligible message
  - engagement settings are enabled for detection
  - an approved engagement target grants `allow_detect = true`
  - quiet hours do not block engagement collection-triggered detection
- Store `analysis_input.engagement_messages` and `analysis_input.engagement_checkpoint` using the
  collection spec shape.
- Update detection sample loading order:
  1. exact `collection_run_id` engagement batch
  2. recent opt-in stored `messages`
  3. compact `sample_messages` artifacts for manual diagnostics and scheduler fallback only

Acceptance:

- Queue payload tests assert `collection_run_id` is optional and serialized.
- Detection tests prove exact `engagement_messages` are preferred over latest sampled artifacts.
- Collection does not pass message text through Redis.
- Detection rejects or skips a `collection_run_id` that belongs to another community.
