# Engagement Embedding Matching Spec

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

## Matching Model

Each active engagement topic has a semantic profile assembled from:

```text
topic.name
topic.description
topic.stance_guidance
topic.example_good_replies
optional future positive trigger-message examples
```

Active topics do not need `trigger_keywords` once semantic selection is enabled, as long as the
topic still has enough profile text to embed. During rollout, topics without trigger keywords should
not trigger the legacy keyword fallback when semantic matching is disabled.

`negative_keywords` remain deterministic exclusions. They should not be treated as a soft semantic
anti-embedding in the first implementation because hard exclusions are easier to reason about and
audit.

Each candidate message is embedded from its sanitized public text plus optional reply context:

```text
source message text
optional capped reply_context
```

The embedding selector computes cosine similarity between the topic profile embedding and each
eligible message embedding. For each topic, it returns at most `K` source messages above the
configured threshold, ordered by:

1. similarity descending
2. message age fit, preferring the configured engagement timing band
3. message date ascending when scores are effectively tied
4. Telegram message ID ascending as a stable final tie-breaker

The drafting model receives only the selected source post or small selected set, not the broad
recent message batch by default.

## Model Choice

Default embedding model:

```text
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=512
```

`text-embedding-3-small` is the default because the selector is a recall-oriented prefilter rather
than the final decision maker. A future deployment may use `text-embedding-3-large` for domains that
need higher semantic precision, but the implementation must allow model and dimension changes
without reusing stale cache rows.

Cache keys must include:

```text
model
dimensions
normalized_text_hash
```

## Default Settings

Recommended settings:

```text
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=512
ENGAGEMENT_SEMANTIC_MATCH_THRESHOLD=0.62
ENGAGEMENT_MAX_SEMANTIC_MATCHES_PER_TOPIC=3
ENGAGEMENT_MAX_EMBEDDING_MESSAGES_PER_RUN=100
ENGAGEMENT_MAX_DETECTOR_CALLS_PER_RUN=5
ENGAGEMENT_MESSAGE_EMBEDDING_RETENTION_DAYS=14
```

The default threshold is intentionally conservative but not final. It should be tuned from observed
operator approvals and a small labeled evaluation set.

## Detection Contract

The semantic selector runs only after the existing engagement gates pass:

- engagement settings are enabled and not `observe`
- approved engagement target grants `allow_detect`
- active topics exist
- recent collection artifacts or stored messages exist
- quiet hours and active reply opportunity dedupe allow detection

Before embedding a message, the worker must apply cheap deterministic gates:

- message has non-empty public text
- source text is capped and sanitized
- message has a Telegram message ID when reply-only sending requires it
- message date is known when timing policy requires it
- message was posted after the engagement account joined
- message is in the configured age window
- message is replyable
- no active reply opportunity already exists for the same community/topic/source
- no configured negative keyword or phrase matches
- no recent sent action cooldown blocks the community/topic

Only messages that pass these gates may be embedded or scored.

## Cache Tables

The first implementation should use Postgres cache tables. A `pgvector` migration may be added
later if batch sizes grow enough to justify indexed vector search.

Recommended table: `engagement_topic_embeddings`

```sql
id                 uuid PRIMARY KEY
topic_id           uuid NOT NULL REFERENCES engagement_topics(id)
model              text NOT NULL
dimensions         int NOT NULL
profile_text_hash  text NOT NULL
embedding          jsonb NOT NULL
created_at         timestamptz NOT NULL DEFAULT now()

UNIQUE (topic_id, model, dimensions, profile_text_hash)
```

Recommended table: `engagement_message_embeddings`

```sql
id                 uuid PRIMARY KEY
community_id       uuid NOT NULL REFERENCES communities(id)
tg_message_id      bigint
source_text_hash   text NOT NULL
model              text NOT NULL
dimensions         int NOT NULL
embedding          jsonb NOT NULL
expires_at         timestamptz NOT NULL
created_at         timestamptz NOT NULL DEFAULT now()

UNIQUE (community_id, tg_message_id, source_text_hash, model, dimensions)
```

If a message has no Telegram message ID, the implementation may cache by
`community_id + source_text_hash + model + dimensions`, but such rows must not be used to create a
sendable reply opportunity unless the source message can later be mapped to a replyable Telegram
message ID.

Embedding vectors should be validated for expected length before storage and after retrieval.

## Embedding Service Contract

Recommended module:

```text
backend/services/engagement_embeddings.py
```

Recommended functions:

```python
def normalize_embedding_text(value: str) -> str:
    ...

def embedding_text_hash(value: str) -> str:
    ...

async def get_or_create_topic_embedding(db, topic, *, model: str, dimensions: int) -> list[float]:
    ...

async def get_or_create_message_embeddings(
    db,
    *,
    community_id,
    messages,
    model: str,
    dimensions: int,
    retention_days: int,
) -> dict[str, list[float]]:
    ...

def cosine_similarity(left: list[float], right: list[float]) -> float:
    ...

async def select_semantic_trigger_messages(
    db,
    *,
    community_id,
    topic,
    messages,
    settings,
) -> list[SemanticTriggerMatch]:
    ...

async def delete_expired_message_embeddings(db, *, now=None) -> int:
    ...
```

Embedding API calls must be batched. The service should dedupe identical normalized texts within a
run before calling the provider.

## Cost Controls

The selector must keep the expensive drafting model rare:

- embed only messages that pass deterministic gates
- batch embedding requests
- reuse cached topic embeddings until topic profile text changes
- reuse cached message embeddings until retention expires
- cap embedded messages per detection run
- cap selected matches per topic
- cap total structured detector calls per community run
- skip detector calls when no message clears the similarity threshold

The embedding cost should be treated as selection overhead, while the structured engagement detector
remains the main cost to protect.

## Prompt And Output Changes

The structured engagement detector input should include semantic selector metadata for audit and
debugging:

```json
{
  "source_post": {
    "tg_message_id": 123,
    "text": "capped public text",
    "message_date": "iso_datetime",
    "reply_context": null
  },
  "semantic_match": {
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 512,
    "similarity": 0.71,
    "threshold": 0.62,
    "rank": 1
  }
}
```

Candidate `model_output` or `prompt_render_summary` should store compact semantic metadata:

```json
{
  "semantic_match": {
    "model": "text-embedding-3-small",
    "dimensions": 512,
    "similarity": 0.71,
    "threshold": 0.62,
    "rank": 1
  }
}
```

Do not store full raw prompts or broad message batches by default.

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
