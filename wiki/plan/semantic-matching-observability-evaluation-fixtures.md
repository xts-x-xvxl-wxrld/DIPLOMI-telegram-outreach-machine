# Semantic Matching Observability + Evaluation Fixtures Plan

## Goal

Complete Slice 5a of engagement embedding matching by making semantic selector behavior auditable
from worker results/logs and by adding a small sanitized evaluation fixture for threshold tuning.

## Scope

- Add aggregate semantic matching counters for cache behavior, rejected messages, selected matches,
  avoided detector calls, and semantic-created reply opportunities.
- Emit structured worker/selector log records with aggregate-only counters.
- Add a lightweight JSONL evaluation fixture using topic/message text that contains no production
  identity data.
- Add tests for the new counters and fixture shape.

## Acceptance

- `engagement.detect` summaries include semantic cache hit/miss, selected-match, avoided-call, and
  semantic-created-opportunity counts.
- Selector logs include cache, rejection, below-threshold, and selection counts.
- Detector logs include total detector calls and semantic-created opportunity counts.
- Evaluation fixtures include both `match` and `no_match` labels and avoid sender identity, phone
  numbers, Telegram user IDs, or person-level scores.

## Status

Completed on 2026-04-21.
