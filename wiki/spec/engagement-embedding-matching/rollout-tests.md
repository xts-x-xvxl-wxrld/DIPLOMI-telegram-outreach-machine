# Engagement Embedding Rollout And Tests

Observability, threshold evaluation, rollout, testing, and safety contracts.

## Purpose

Engagement embedding matching replaces brittle manual keyword detection with a low-cost semantic
selector for reply opportunities.

The selector is only a first-pass gate. It identifies source posts that are semantically close to an
operator-approved engagement topic. The existing engagement detector still decides whether the
moment is useful enough to draft a public reply, and the operator still approves every send.

Target flow:

```text
fresh collected messages
  -> deterministic eligibility and safety gates
  -> cached embedding similarity selector
  -> top source posts per topic
  -> structured engagement detector and draft model
  -> operator-reviewed reply opportunity
```
## Goals

- Improve topic recall beyond exact keywords and phrase matches.
- Keep model spend low by using embeddings as a cheap selector before any drafting call.
- Preserve the engagement module's public-only, approval-gated, auditable workflow.
- Keep build complexity modest by starting with Postgres-backed embedding caches and Python cosine
  scoring over small detection batches.
- Make topic matching tunable through thresholds, caps, examples, and observed operator outcomes.
## Non-Goals

- No automatic sending.
- No person-level scoring, ranking, profiling, or persuasion labels.
- No direct messages.
- No new Telegram scraping path inside engagement detection.
- No replacement for the structured draft model's `should_engage = false` decision.
- No vector database service in the first implementation.
- No business logic in collection workers.
## Product Boundary

Embedding matching is part of `engagement.detect`.

Collection may continue to write compact public message artifacts or optional stored messages, but
collection must not embed, score, classify, draft, notify, join, or send. The engagement worker owns
topic selection, embedding calls, cache writes, similarity scoring, model-call caps, and reply
opportunity creation.

The semantic score is a community-message-to-topic matching signal only. It must not be exposed as a
quality score for an individual user or used to prioritize people.
## Observability

Structured logs and metrics should count:

- topic embeddings created
- message embeddings created
- embedding cache hits
- embedding cache misses
- messages rejected by deterministic gates
- messages rejected by negative exclusions
- messages below semantic threshold
- semantic matches selected
- detector calls avoided
- detector calls made
- reply opportunities created from semantic matches
- operator approvals and rejections by similarity band

Similarity bands should be aggregate-only. They must not become person-level scores.

The first observability slice exposes these counts in the `engagement.detect` worker result and
emits structured log records:

- `engagement.semantic_selector` with aggregate cache, rejection, below-threshold, selected-match,
  and avoided-call counters for a community/topic selector run
- `engagement.detect_summary` with aggregate detector calls and semantic-created reply opportunity
  counts for a community detection run

The logs must not include sender identity, phone numbers, raw broad prompt batches, or person-level
scores. Similarity values remain compact candidate metadata only for selected source posts.

The rollout review surface summarizes semantic-created reply opportunities by similarity band from
stored candidate metadata. It is aggregate-only: it may show counts, approval rates, pending counts,
expired counts, and average similarity per band, but it must not show candidate IDs, source message
text, sender identity, phone numbers, or person-level scores.
## Threshold Evaluation

Maintain a small evaluation set outside production user identity data:

```text
topic profile
sanitized message text
human label: match | no_match
similarity score
detector decision
operator outcome when available
```

Use the eval set to tune:

- default threshold
- per-topic threshold overrides, if added later
- max selected matches per topic
- whether positive trigger-message examples improve recall

Operator approval rate is useful feedback, but it is not the only metric. A low approval rate may
mean the draft model is weak, the topic is vague, or the threshold is too loose.

`GET /api/engagement/semantic-rollout` and `/engagement_rollout [window_days]` provide the first
operator review surface for this tuning loop. Approved, sent, and failed-after-approval reply
opportunities count as approved operator outcomes; rejected rows count as rejected outcomes; pending
and expired rows are shown separately as operational context.

The initial fixture lives at `tests/fixtures/engagement_semantic_eval.jsonl`. It is intentionally
small and synthetic/sanitized: topic profile, sanitized message text, human label, similarity score,
detector decision, and optional operator outcome. It must include both `match` and `no_match`
labels and must not contain sender usernames, Telegram user IDs, phone numbers, or person-level
scores.
## Rollout

Phase 1: Add docs, settings, cache tables, and embedding service tests.

Phase 2: Add semantic selector behind a feature flag while keeping keyword prefilter as fallback.

During this phase, semantic-only topics may exist in admin data, but they should stay inert until
the semantic-selector feature flag is enabled for detection.

Phase 3: Log semantic scores and compare selector behavior against current keyword matching.

Phase 4: Make semantic selector the default first-pass matcher and keep keyword triggers only as
optional boost or emergency fallback.

Phase 5: Consider `pgvector` only if Python scoring over bounded batches becomes a real bottleneck.
## Testing Contract

Minimum tests:

- topic profile text changes invalidate the topic embedding cache
- message embedding cache is reused for identical normalized text/model/dimensions
- embedding rows reject wrong vector dimensions
- selector skips model calls when all similarities are below threshold
- selector returns stable top-K ordering above threshold
- negative keyword exclusions override high semantic similarity
- no sender username, Telegram user ID, phone number, or private account metadata enters embedding
  text
- detector receives only selected source posts and compact semantic metadata
- total detector calls are capped per run
- reply opportunity dedupe still uses community/topic/source message identity
- cache retention cleanup removes expired message embeddings
## Safety Rules

- Embedding matching is not permission to send.
- Human approval remains required before every send in MVP.
- Semantic scores are message/topic fit signals only.
- No person-level scores, labels, or rankings.
- No direct messages.
- No hidden manipulation or fake consensus.
- All selected opportunities remain auditable.
