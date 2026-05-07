# Engagement Test Community Wait Bypass

## Problem

The engagement send path currently applies the same time-based waits to every
community: delayed send scheduling, post-join warmup, and spacing/cooldown
checks. That is desirable for production communities, but it slows down manual
testing when operators need a small allowlisted set of test communities to send
immediately.

## Plan

1. Add an explicit environment-driven allowlist for test communities whose
   wait periods are bypassed.
2. Use the allowlist in engagement timing helpers so delayed send scheduling and
   post-join warmup can be skipped for those communities.
3. Apply the same bypass to send spacing/cooldown checks while keeping approval,
   permissions, and hard daily/root-opportunity caps intact.
4. Cover the bypass with focused helper and send-worker regressions, then update
   the engagement account-behavior and scheduling specs.

## Verification

- `python scripts/check_fragmentation.py`
- `ruff check .`
- `pytest -q`
