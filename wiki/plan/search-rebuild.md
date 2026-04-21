# Search Rebuild Plan

## Goal

Capture a clean-sheet design for Telegram community search that is stronger than the current
seed-first-only discovery slice and can later guide implementation without being constrained by the
current code shape.

## Why This Slice

The current app has strong primitives for manual seed intake, resolution, and snapshotting, but the
broader notion of "search" is still fragmented. This plan creates a dedicated spec so future work
can distinguish:

- manual seed intake
- direct Telegram handle intake
- query-driven community search
- post/message search
- graph expansion from strong hits
- ranking and review evidence

## Planned Output

- Add a new spec at `wiki/spec/search-rebuild.md`.
- Describe a first-class `search_run` model rather than overloading seed groups.
- Define query planning, retrieval adapters, evidence storage, ranking, and operator review.
- Keep seeds in the design as one search input and one graph root, not the only discovery mode.
- Record the new design in `wiki/index.md` and `wiki/log.md`.

## Non-Goals

- No implementation in this slice.
- No migration plan or schema rollout details yet.
- No commitment that the new search model is the active MVP path today.

## Acceptance

- The wiki contains a standalone spec for the clean-sheet Telegram search rebuild.
- The index links to the new spec and plan.
- The log records the addition with enough context for future sessions.
