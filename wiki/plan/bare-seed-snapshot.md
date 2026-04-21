# Bare Seed Snapshot Plan

## Goal

Pause automatic or operator-facing expansion for now.

The active path should be:

```text
CSV upload
  -> seed_groups + seed_channels
  -> seed.resolve
  -> resolved seed communities
  -> community.snapshot for those seed communities
  -> community metadata, snapshots, users, and community_members persisted
```

Seeds are assumed to be high-quality examples supplied by the operator. The MVP can therefore
snapshot the exact imported communities before trying to discover adjacent communities.

## Scope

- Keep CSV seed import unchanged.
- Keep `seed.resolve` as the step that maps public Telegram usernames to `communities`.
- After a seed resolves, queue `community.snapshot` for the resolved seed community.
- Implement a bare `community.snapshot` worker that fetches Telegram metadata and visible members.
- Persist users and community membership safely without phone numbers or person-level scores.
- Mark analysis as skipped for this bare member import path unless message analysis is added later.

## Non-Goals

- No seed expansion.
- No generic discovery.
- No OpenAI calls.
- No raw message intake.
- No private invite-link scraping.
- No person-level scoring or prioritization.

## Safety Notes

- Member identity fields are stored once in `users`.
- `community_members` stores only membership/activity status, not scores.
- Phone numbers are never read or persisted.
- Duplicate members are upserted by Telegram user id and `(community_id, user_id)`.
- Snapshot failures should create failed `collection_runs` rows instead of partially pretending success.

## Implementation Steps

1. Add snapshot persistence service for metadata snapshots and visible members.
2. Add Telethon snapshot adapter for full community info and participant iteration.
3. Wire `community.snapshot` dispatch to the real worker.
4. Queue initial snapshot jobs for communities resolved by `seed.resolve`.
5. Hide expansion from bot-facing seed commands while keeping old expansion code dormant.
6. Update specs and tests.
