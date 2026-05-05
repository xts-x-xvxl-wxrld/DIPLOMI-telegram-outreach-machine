# Engagement Detect Warmup Drafts

## Problem

Freshly joined engagement communities currently block `engagement.detect` for
the full post-join warmup window. In live testing this makes new inbound
messages look ignored, even though collection succeeds and operators only need a
draft to review. Sending already has its own warmup preflight, so draft creation
during warmup is unnecessarily stricter than public posting.

## Plan

1. Remove the post-join warmup skip from `engagement.detect` while keeping the
   existing joined-membership requirement.
2. Keep `engagement.send` warmup preflight unchanged so no public reply can send
   before acclimation ends.
3. Replace the detect-worker warmup skip regression with a regression that
   asserts draft creation can still happen during warmup.
4. Update the engagement account-behavior spec and queue/docs to describe
   "draft now, send later" warmup behavior.

## Verification

- `python scripts/check_fragmentation.py`
- `ruff check .`
- `pytest -q`
