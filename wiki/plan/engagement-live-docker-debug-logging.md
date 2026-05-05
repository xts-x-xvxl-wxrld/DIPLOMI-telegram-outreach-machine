# Engagement Live Docker Debug Logging

## Goal

Make the engagement pipeline easier to live-test in local Docker by emitting
high-signal runtime logs at each major decision point.

## Scope

- Enable worker entrypoints to surface INFO-level logs in Docker output.
- Add stage logs for engagement scheduling, collection, detection, joining, and
  sending.
- Keep logs focused on IDs, counts, skip reasons, and status changes without
  dumping full message text or reply bodies.

## Steps

1. Confirm the active engagement worker entrypoints and observability contract.
2. Configure worker bootstraps so existing INFO logs are visible in Docker.
3. Add missing runtime logs where the pipeline still goes silent:
   - scheduler target selection and enqueue/skip decisions
   - collection account acquisition, collection summary, read acknowledgement,
     and detect enqueue result
   - detect topic/sample counts, trigger selection counts, detector decisions,
     and candidate creation outcomes
   - send preflight checkpoints, account acquisition, source verification, and
     final action outcome
   - Telethon adapter entry/exit checkpoints for join/send/read flows
4. Run focused local validation and a Docker build/live run to confirm the new
   logs are visible.

## Acceptance Criteria

- `docker compose` worker and scheduler logs show INFO-level engagement
  checkpoints without code changes outside the requested area.
- A live engagement run exposes enough detail to tell whether a job skipped,
  progressed, or failed and why.
- Logs do not include raw full reply bodies or large message dumps.
