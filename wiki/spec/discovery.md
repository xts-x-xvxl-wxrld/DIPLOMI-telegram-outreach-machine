# Discovery Spec

## Purpose

Discovery is seed-first for the active MVP, with graph expansion paused for the current slice.

The operator supplies example Telegram communities as named `seed_groups`. The app resolves those
examples with `seed.resolve`, then collects metadata and visible members for those exact resolved
seed communities. A seed group is the primary intent object for this slice: it means "these are
high-quality communities worth importing and collecting."

Audience-brief discovery is not the primary path. `brief.process` and `discovery.run` may remain as
legacy or future optional capabilities, but they should not drive the next implementation slice.

Discovery does not join private communities, collect raw message history, call OpenAI, or decide
final relevance.

## Active MVP Flow

```text
CSV upload
  -> seed_groups + seed_channels
  -> seed.resolve
  -> resolved seed communities
  -> collection.run
  -> metadata snapshots + users + community_members
```

Seed import stores public-looking usernames and links first. Resolution is the boundary where a
public seed becomes a real `communities` row with a Telegram `tg_id`. Initial collection is the
boundary where group info and visible members are persisted safely. Expansion remains documented as
a future/dormant capability, but it is not the active next step.

## Intent Model

`seed_groups` carry operator intent.

Examples:

- `Hungarian SaaS founders`
- `Academic English thesis help`
- `Telegram marketing communities in Central Europe`

The group name and optional description should be preserved in candidate listings and match
reasons. Candidates discovered from a seed group should be traceable back to:

- seed group
- seed channel row
- resolved source community
- evidence type
- evidence value

This provenance lives in `community_discovery_edges` for expansion results. Manually resolved seed
communities are traceable through `seed_channels.community_id`.

## Source Strategy

Allowed source families:

- manual seed groups imported through CSV and resolved through `seed.resolve`
- future graph expansion from resolved seeds through linked discussions, forwards, mentions, and Telegram links
- future public web-search adapters that return public Telegram identifiers for import/resolution
- future Telegram account-backed search adapters, after account-rate behavior is measured

Disallowed source families:

- TGStat or TGStat-derived APIs
- private invite-link scraping
- people search or person-level scoring
- raw message collection inside discovery
- OpenAI-generated relevance decisions inside discovery

## Candidate Normalization

All sources eventually normalize to `communities`.

Before a row is written to `communities`, the app should resolve public usernames or links through
Telegram where possible so `tg_id` is the dedupe key. Resolution writes:

- `source = 'manual'` for imported seeds
- `source = 'expansion'` for graph-discovered communities
- `source = 'web_search'` or `source = 'telegram_search'` only for future adapter results
- `status = 'candidate'` only for new communities
- `brief_id` only when an optional future brief context is explicitly attached
- `match_reason` with plain-language evidence

## Deduplication

Preferred dedupe order before resolution:

1. lowercase normalized username
2. canonical public Telegram URL
3. lowercase title plus source evidence URL

Preferred dedupe order after resolution:

1. `tg_id`
2. lowercase normalized `username`

When an existing community is found:

- update missing or stale metadata
- merge additional source evidence into the match explanation where useful
- preserve existing `rejected`, `approved`, `monitoring`, or `dropped` status
- never overwrite operator-controlled `store_messages`

## Candidate Ordering

Discovery ranking should be deterministic and explainable. It is an operator sorting signal, not a
relevance score and not a person-level score.

Seed-first ordering signals:

- linked discussion evidence
- forward source evidence
- Telegram link evidence
- mention evidence
- number of distinct seeds in the same seed group that found the same candidate
- number of distinct evidence events
- member count or public activity hints when available
- whether the operator has already rejected the community

Initial scoring guidance for candidate ordering:

```text
linked_discussion: +50
forward_source: +25
telegram_link: +15
mention: +10
each additional source seed in same group: +20
each repeated evidence event: +3, capped
already rejected: hide by default or sort last
```

Scores are computed for display/sorting only. They should not be stored as durable relevance
judgments unless a later spec adds a community-level ranking artifact.

## Future Brief Layer

Audience briefs may return later as optional context:

- attach a `brief_id` to a seed expansion run
- use brief fields to filter or sort seed-group candidates
- include brief context in collection analysis
- run public web-search adapters to produce additional seed candidates

Briefs must not replace seed-group provenance. If both are present, seed-group evidence remains the
primary explanation for why a candidate entered the app.

## Safety Rules

- Discovery finds communities, not people.
- No person-level scoring.
- No OpenAI calls in discovery.
- No raw Telegram message collection in discovery.
- Telegram account-backed discovery must use the account manager and respect flood-wait behavior.
