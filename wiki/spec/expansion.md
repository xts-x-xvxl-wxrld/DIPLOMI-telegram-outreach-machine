# Expansion Spec

## Purpose

Expansion grows the candidate community graph from an imported manual seed batch.

It uses Telethon to inspect accessible public Telegram channels and groups, discover related
communities, and add those communities back into the candidate set for operator review.

Expansion is the core seed-first discovery step. The operator imports a CSV into a `seed_group`,
resolves that batch with `seed.resolve`, and then expands the batch with `/expandseeds`. The worker
inspects the resolved `communities` rows, but the expansion request and match evidence must keep the
seed group context instead of becoming anonymous expansion over arbitrary saved channels.

Generic `expansion.run` over arbitrary community IDs may exist later for direct operator workflows,
but the MVP should prioritize `seed.expand`.

## Inputs

Seed-first expansion receives:

```json
{
  "seed_group_id": "uuid",
  "brief_id": "uuid-or-null",
  "depth": 1,
  "requested_by": "telegram_user_id_or_operator"
}
```

The batch job reads `seed_channels` in that seed group where `status = 'resolved'` and
`community_id IS NOT NULL`. `brief_id` is optional future context; it may be null for the active MVP.

Generic expansion may later receive:

```json
{
  "brief_id": "uuid-or-null",
  "community_ids": ["uuid"],
  "depth": 1,
  "requested_by": "telegram_user_id_or_operator"
}
```

## Responsibilities

- Acquire a Telegram account lease through the account manager.
- Inspect linked discussion groups where available.
- Inspect recent public posts for forwarded-from channels.
- Extract Telegram mentions, `t.me` links, and `telegram.me` links from recent posts, captions, descriptions, and pinned messages when available.
- Add newly discovered communities as candidates.
- Update metadata for inspected communities.
- Preserve seed-group context when expansion starts from an imported batch.
- Write provenance edges for every unique seed/source/target/evidence tuple.
- Produce enough aggregate evidence for operator-facing candidate ordering.

## Non-Responsibilities

- No OpenAI calls.
- No community relevance scoring.
- No raw message collection beyond the small inspection window needed for relation discovery.
- No collection scheduling.
- No direct outreach.
- No CSV seed-row resolution; that belongs to `seed.resolve`.
- No expansion from unresolved seed rows.
- No durable relevance score. Expansion may produce display ordering signals only.

## Graph Inspection Logic

MVP expansion depth is `1`. For each resolved seed community:

1. Load the source community entity and public metadata.
2. If it is a broadcast channel with a linked discussion group, resolve and add that discussion.
3. Inspect a capped recent post/message window, initially 50-100 items per seed.
4. Record forwarded-from channels/groups as candidates when Telegram exposes the source.
5. Extract public Telegram usernames and links from message text, captions, pinned messages, and descriptions.
6. Resolve extracted identifiers into communities before writing candidates.
7. Deduplicate candidates by Telegram `tg_id`.
8. Create `community_discovery_edges` for each unique evidence item.

The adapter must cap work per seed group so one batch cannot exhaust account health. Initial caps:

- max 100 recent posts/messages per seed
- max 50 extracted public identifiers per seed
- max 200 discovered identifiers per seed group before dedupe

These caps can be tuned after the first real seed-group experiments.

## Candidate Writes

Newly discovered communities are written to `communities` with:

- `source = 'expansion'`
- `status = 'candidate'`
- `brief_id` from the expansion payload when present
- `match_reason` based on graph evidence, such as linked discussion, forward source, mention, or Telegram link

For batch-scoped seed expansion, `match_reason` must also include the seed group name and, when
known, the resolved seed community that produced the evidence.

Existing operator decisions must be preserved. Expansion must not reset `rejected`, `approved`,
`monitoring`, or `dropped` communities back to `candidate`.

## Candidate Ordering Signals

Expansion should expose deterministic ordering signals for seed-group candidate review. These are
display aids, not durable relevance scores.

Recommended initial weights:

```text
linked_discussion: +50
forward_source: +25
telegram_link: +15
mention: +10
each additional resolved source seed in the same group: +20
each repeated evidence item: +3, capped
```

Candidates discovered by multiple seeds in the same seed group should sort above candidates found by
one weak mention. Rejected candidates should be hidden by default or sorted last.

## Provenance Writes

Batch-scoped seed expansion writes one `community_discovery_edges` row for each unique
seed/source/target/evidence tuple:

- `seed_group_id` points to the imported batch.
- `seed_channel_id` points to the resolved seed row that produced the evidence.
- `source_community_id` points to the resolved seed community inspected by the adapter.
- `target_community_id` points to the discovered or updated community.
- `evidence_type` and `evidence_value` store compact graph evidence.

Duplicate evidence should be skipped instead of writing another edge.

Evidence types for the first adapter:

- `linked_discussion`
- `forward_source`
- `telegram_link`
- `mention`
- `profile_link`
- `pinned_link`

## Account Handling

Expansion uses:

```python
account_manager.acquire_account(purpose="expansion")
```

Workers must release the account in a `finally` block.

Flood waits, banned sessions, inaccessible communities, and no-account states follow the account
manager and queue specs.

## Depth

MVP supports `depth = 1`.

Higher depth expansion should wait until candidate quality and account rate limits are understood.

## Safety Rules

- Expansion finds communities, not people.
- No person-level scores.
- No business logic from collection or analysis.
- Do not join private communities automatically.
