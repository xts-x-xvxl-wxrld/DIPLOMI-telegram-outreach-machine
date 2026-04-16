# Seed-First Discovery Plan

## Goal

Make seed groups the primary discovery and review workflow.

The operator should be able to import example Telegram communities, resolve them, expand from them,
review candidates by seed group, and monitor approved communities without creating an audience brief.

## Rationale

Real example communities are stronger intent signals than a natural-language brief. They provide
concrete graph roots, allow explainable discovery, and let the operator judge results by provenance:
which seed led to which candidate and why.

Briefs remain useful later as optional context for filtering, sorting, web-search adapters, and
analysis. They should not block the MVP.

## Target Flow

```text
CSV upload
  -> seed_groups + seed_channels
  -> seed.resolve
  -> seed.expand
  -> seed-group candidate review
  -> approval to monitoring
  -> collection
  -> analysis
```

## Product Contract

- `/seeds` lists seed groups and resolution/expansion status.
- `/resolveseeds <seed_group_id>` resolves public usernames and links into `communities`.
- `/expandseeds <seed_group_id>` expands from resolved seed communities.
- `/candidates <seed_group_id>` lists candidates for that seed group.
- Candidate cards explain graph evidence, not abstract keyword matching.
- Approving a candidate moves it to `monitoring` and queues initial collection.
- Rejecting a candidate preserves the decision across future expansion runs.

## Expansion Logic

For each resolved seed community, inspect a capped public window and discover candidates from:

- linked discussion groups
- forwarded-from channels/groups
- public Telegram links in descriptions, pinned messages, post text, and captions
- public `@username` mentions

Resolve every discovered identifier before writing a `communities` row. Write
`community_discovery_edges` for each unique seed/source/target/evidence tuple.

## Candidate Ordering

Use deterministic display-only scoring:

```text
linked_discussion: +50
forward_source: +25
telegram_link: +15
mention: +10
each additional resolved source seed in the same group: +20
each repeated evidence item: +3, capped
```

This is only for operator sorting. It is not a durable relevance score and never applies to people.

## Implementation Steps

1. Implement the real `TelethonSeedExpansionAdapter`.
2. Add a seed-group candidate query that combines manually resolved seeds and expansion targets.
3. Add API response schemas for seed-group candidate evidence summaries.
4. Update the bot `/candidates` command to take a `seed_group_id`.
5. Run one narrow real seed-group experiment with 10-25 seed communities.
6. Inspect result quality and tune caps, evidence extraction, and candidate ordering.

## Non-Goals

- No brief-first discovery for this slice.
- No OpenAI calls in discovery or expansion.
- No private invite-link crawling.
- No person-level scores.
- No outreach automation.
- No raw message collection during expansion beyond the small inspection window needed for graph evidence.
