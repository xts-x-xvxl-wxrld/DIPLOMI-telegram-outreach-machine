# Discovery Snapshot Rename Plan

## Goal

Separate discovery metadata/member capture from engagement collection vocabulary.

Discovery should say **community snapshot**. Engagement should keep **collection** for recent-message
intake that feeds reply opportunity detection.

## Scope

- Rename the discovery worker job from `collection.run` to `community.snapshot`.
- Rename discovery-side service, worker, adapter, bot, API, and test vocabulary from collection to
  snapshot.
- Keep `collection.run` reserved for engagement message intake.
- Keep the `collection_runs` database table for now as the shared durable run/artifact boundary.

## Decisions

- No database table rename in this slice.
- No migration for `collection_runs` in this slice.
- Bot/operator discovery commands use `/snapshot <community_id>` instead of `/collect`.
- API discovery endpoints use `/snapshot-jobs` and `/snapshot-runs`.
- Engagement docs continue to use collection.

## Acceptance

- Seed resolution queues `community.snapshot` jobs for resolved seed communities.
- Discovery snapshot code no longer imports the former discovery collection modules.
- Wiki docs explain that discovery snapshots and engagement collection are separate concepts.
- Tests cover the renamed payload, queue helper, worker, bot client, and formatting contracts.
