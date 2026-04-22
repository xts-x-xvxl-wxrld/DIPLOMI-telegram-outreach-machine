# Engagement Embedding Matching Spec

Top-level routing contract for semantic engagement topic matching. Details live in `wiki/spec/engagement-embedding-matching/`.

## Responsibility

- Cache topic and message embeddings for community-level matching.
- Use embeddings as a selector before drafting, not as an autonomous send decision.
- Keep rollout observable and threshold-evaluable.

## Code Map

- `backend/services/engagement_embeddings.py` - embedding cache and selector service.
- `alembic/versions/20260421_0010_engagement_embeddings.py` - embedding schema.
- `tests/test_engagement_embeddings.py` - embedding behavior tests.
- `tests/fixtures/engagement_semantic_eval.jsonl` - sanitized eval fixtures.

## Shards

- [Matching and Cache](engagement-embedding-matching/matching-cache.md)
- [Rollout and Tests](engagement-embedding-matching/rollout-tests.md)
