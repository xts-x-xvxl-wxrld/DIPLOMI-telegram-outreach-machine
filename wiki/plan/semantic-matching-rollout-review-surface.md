# Semantic Matching Rollout Review Surface Plan

## Goal

Complete Slice 5b of engagement embedding matching by giving operators an aggregate review surface
for semantic-selector rollout outcomes.

The surface should answer:

- how many semantic-created reply opportunities are being reviewed
- how approval and rejection outcomes distribute by similarity band
- whether pending or expired opportunities are accumulating

## Scope

- Add an aggregate backend service that reads semantic metadata already stored on engagement
  candidates.
- Add an authenticated API endpoint for the rollout summary.
- Add a Telegram bot command that renders the aggregate summary for operators.
- Keep all output aggregate-only: no source messages, sender identity, candidate IDs, phone
  numbers, or person-level scores.

## Acceptance

- Operators can review semantic candidate outcomes by similarity band.
- Approved, sent, and failed-after-approval rows count as approved operator outcomes.
- Rejected rows count as rejected operator outcomes.
- Pending and expired rows remain visible as non-reviewed operational context.
- The API and bot responses do not expose raw source text, sender identity, phone numbers, candidate
  IDs, or person-level scores.

## Status

Completed on 2026-04-21.

## Implementation Notes

- Backend service: `summarize_semantic_rollout` aggregates semantic metadata stored on engagement
  candidates.
- API route: `GET /api/engagement/semantic-rollout`.
- Focused tests cover API aggregation, bot API-client routing, bot handler rendering, and
  aggregate-only formatting.
