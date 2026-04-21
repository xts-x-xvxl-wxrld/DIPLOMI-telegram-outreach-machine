# Engagement Embedding Matching Plan

## Goal

Replace the current manual keyword-only engagement prefilter with a cached embedding-based semantic
selector that improves topic recall while reducing unnecessary drafting-model calls.

The first implementation should be conservative:

```text
deterministic eligibility gates
  -> cached topic/message embeddings
  -> cosine similarity top-K selector
  -> existing structured engagement detector
  -> operator-reviewed reply opportunity
```

## Current Context

`engagement.detect` currently reads compact collection artifacts or stored messages, checks active
topics, applies keyword and negative-keyword filtering, and calls the OpenAI engagement model only
when keyword signal exists.

That cost-control shape is good and should stay. The weak point is recall: users rarely phrase a
discussion exactly like the configured keyword list. Embeddings should replace the brittle trigger
match while keeping deterministic safety gates, dedupe, timing rules, and the final model decision.

## Design Decisions

- Use `text-embedding-3-small` by default.
- Use reduced dimensions, initially 512, to lower storage and scoring cost.
- Store topic and message embeddings in Postgres cache tables for the first implementation.
- Score bounded detection batches in Python using cosine similarity.
- Keep negative keywords as deterministic hard exclusions.
- Keep the structured detector as the final `should_engage` and draft decision.
- Do not add `pgvector` until bounded Python scoring is proven insufficient.
- Never expose semantic similarity as a person-level score.

## Slice 1: Wiki And Contracts

Status: completed.

Tasks:

- Add `wiki/spec/engagement-embedding-matching.md`.
- Add this plan file.
- Update `wiki/index.md`.
- Cross-link `wiki/spec/engagement.md` so future detector work sees the semantic-selector contract.
- Append `wiki/log.md`.

Acceptance:

- Future agents can find the embedding selector spec from the wiki index.
- The engagement spec clearly states that keyword matching is being replaced by a semantic selector.
- Database cache tables and implementation phases are described before code work begins.

## Slice 2: Settings And Schema

Status: pending.

Add settings:

```text
OPENAI_EMBEDDING_MODEL
OPENAI_EMBEDDING_DIMENSIONS
ENGAGEMENT_SEMANTIC_MATCH_THRESHOLD
ENGAGEMENT_MAX_SEMANTIC_MATCHES_PER_TOPIC
ENGAGEMENT_MAX_EMBEDDING_MESSAGES_PER_RUN
ENGAGEMENT_MAX_DETECTOR_CALLS_PER_RUN
ENGAGEMENT_MESSAGE_EMBEDDING_RETENTION_DAYS
```

Add Alembic migration and models for:

- `engagement_topic_embeddings`
- `engagement_message_embeddings`

Acceptance:

- Migration upgrades and downgrades cleanly.
- Cache uniqueness includes model, dimensions, and normalized text hash.
- Message cache rows can expire.

## Slice 3: Embedding Service

Status: pending.

Add `backend/services/engagement_embeddings.py` with:

- text normalization and hashing
- batched OpenAI embedding calls
- topic embedding cache lookup/create
- message embedding cache lookup/create
- cosine similarity
- stable top-K semantic trigger selection

Acceptance:

- Identical normalized texts are embedded only once per run.
- Cache hits avoid provider calls.
- Wrong vector dimensions fail closed.
- No private sender identity is embedded.

## Slice 4: Detector Integration

Status: pending.

Integrate the selector into `backend/workers/engagement_detect.py` behind a feature flag or setting.

Acceptance:

- Deterministic eligibility gates run before embeddings.
- Semantic matches replace keyword matches when enabled.
- Keyword prefilter remains available as a fallback during rollout.
- Detector calls are capped per community run.
- Candidate metadata stores compact semantic match details.

## Slice 5: Evaluation And Rollout

Status: pending.

Add lightweight evaluation fixtures and metrics for threshold tuning.

Acceptance:

- Tests cover below-threshold skips and top-K match selection.
- Logs count cache hits, cache misses, selected matches, avoided detector calls, and created reply
  opportunities.
- Operator approval/rejection outcomes can be reviewed by similarity band without exposing
  person-level scoring.

## Open Questions

- Should thresholds eventually be global only, or allow per-topic overrides?
- Should topic profiles include separate positive trigger-message examples beyond good reply
  examples?
- Should `pgvector` be introduced once stored-message communities grow, or should detection stay
  limited to bounded recent batches?

## Rollback Plan

- Disable semantic matching through settings and fall back to keyword prefiltering.
- Keep cache tables for inspection and later reuse.
- Do not alter reply opportunity, review, or send semantics during rollback.
