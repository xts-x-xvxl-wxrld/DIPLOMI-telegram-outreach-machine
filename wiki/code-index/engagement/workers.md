# Engagement Workers Map

## Scope

This shard covers background execution for engagement scheduling, target
resolution, joins, detection, sends, and Telethon adapter seams.

## Read First

- `backend/workers/engagement_scheduler.py`
- `backend/workers/engagement_target_resolve.py`
- `backend/workers/community_join.py`
- `backend/workers/engagement_detect.py`
- `backend/workers/engagement_detect_process.py`
- `backend/workers/engagement_send.py`
- `backend/workers/telegram_engagement.py`

## Scheduling and timing

- `backend/workers/engagement_scheduler.py`
  - detection scheduler tick
  - collection scheduler tick
  - account-health refresh scheduler tick
  - quiet-hours gating
  - detection/collection target loading and skip reasons
- `backend/services/engagement_account_behavior.py`
  - send delay, warmup, read-jitter, opportunity cadence, health-refresh
    constants
- `backend/services/engagement_due_state.py`
  - Redis due-state keys and next-due decisions
- `backend/workers/engagement_send_cadence.py`
  - per-account and per-conversation opportunity cadence checks

## Target resolve and join

- `backend/workers/engagement_target_resolve.py`
  - resolves submitted engagement targets against Telegram entities
- `backend/workers/community_join.py`
  - membership join orchestration
  - preferred account selection
  - join-result recording and failed-join audit
- `backend/workers/telegram_engagement.py`
  - Telethon adapter for joins, sends, source preflight, read receipts, typing,
    and account-status exception mapping

## Detection pipeline

- `backend/workers/engagement_detect.py`
  - export/facade module for the split detection implementation
- `backend/workers/engagement_detect_types.py`
  - detection DTOs, prompt instructions, protocol types
- `backend/workers/engagement_detect_samples.py`
  - collection-run and stored-message sample loading
  - community context loading
- `backend/workers/engagement_detect_prompt.py`
  - prompt input assembly, style-bundle loading, summary shaping
- `backend/workers/engagement_detect_selection.py`
  - trigger candidate prefiltering and duplicate suppression
- `backend/workers/engagement_detect_openai.py`
  - model call wrapper
- `backend/workers/engagement_detect_process.py`
  - end-to-end detect job orchestration, semantic matching, candidate creation,
    deadline inference, and public-safe logging

## Send pipeline

- `backend/workers/engagement_send.py`
  - send orchestration
  - candidate/action loading
  - idempotent action reservation
  - limit checks
  - success/failure/skipped recording
- `backend/workers/telegram_engagement.py`
  - actual Telegram send and account exception mapping

## Boundary notes

- Queue payload/job ID shape lives in `backend/queue/`.
- Scheduling decisions are split between worker orchestration and
  `backend/services/engagement_*` helpers.
- `backend/workers/telegram_engagement.py` is the main adapter seam for tests
  and future transport swaps.
