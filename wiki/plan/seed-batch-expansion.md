# Seed Batch Expansion Plan

## Goal

Make manual seed batches (`seed_groups`) a first-class expansion target.

Seed resolution still writes resolved seeds into `communities`, but expansion from an imported CSV
batch should remain anchored to the batch rather than becoming generic expansion over arbitrary
saved community IDs.

## Rationale

Operators import seeds as curated batches with intent and context. Expansion should preserve that
context so discovered communities can be traced back to:

- the seed group name
- the resolved seed channel that produced the evidence
- the expansion evidence type, such as linked discussion, forward source, mention, or Telegram link

This keeps manual seed workflows separate from generic candidate/community expansion.

## Queue Contract

Add a batch-scoped job:

```json
{
  "seed_group_id": "uuid",
  "brief_id": "uuid-or-null",
  "depth": 1,
  "requested_by": "telegram_user_id_or_operator"
}
```

The worker reads resolved `seed_channels` for the batch and expands from their linked
`communities` rows. The job must fail clearly with `no_resolved_seed_communities` if the batch has
no resolved seed rows.

## Writes

Discovered communities are still written to `communities`, but with batch-aware context:

- `source = 'expansion'`
- `status = 'candidate'` for new communities
- `brief_id` from the payload when present
- `match_reason` includes the seed group name and expansion evidence

Existing operator decisions must be preserved. Batch expansion must not reset `rejected`,
`approved`, `monitoring`, or `dropped` communities back to `candidate`.

## API Contract

`POST /api/seed-groups/{seed_group_id}/expansion-jobs` should enqueue the batch-scoped expansion
job instead of flattening the group into a generic community-id expansion request.

Generic community expansion may still exist for later direct operator workflows, but `/expandseeds`
must remain seed-batch-aware.

## Non-Goals

- No CSV parsing; import remains in seed import.
- No seed resolution; unresolved rows must go through `seed.resolve`.
- No OpenAI calls.
- No snapshot, collection, or monitoring side effects.
- No person-level scoring.

## Implementation Steps

1. Add a `seed.expand` queue payload and enqueue helper.
2. Change the seed-group expansion API endpoint to queue `seed.expand`.
3. Add a worker/service that loads resolved seed rows for a seed group and delegates graph
   inspection per resolved seed.
4. Persist discovered communities with seed-group-aware match reasons.
5. Add fake Telethon/adapter tests for batch expansion, empty resolved batch, duplicate discoveries,
   existing operator statuses, and account release behavior.
