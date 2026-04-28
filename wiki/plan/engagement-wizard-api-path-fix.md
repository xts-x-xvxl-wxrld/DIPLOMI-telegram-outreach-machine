# Engagement Wizard API Path Fix

## Goal

Fix the task-first Telegram engagement wizard so creating a community draft uses the documented
`/api/engagements` routes instead of accidentally requesting `/api/api/engagements`.

## Slice

- Reproduce the staging failure and capture the exact wizard request sequence.
- Keep `POST /api/engagement/targets` as the Step 1 target-intake call.
- Remove the duplicated `/api` prefix from the wizard-only bot API client methods for
  `create_engagement`, `patch_engagement`, `put_engagement_settings`,
  `wizard_confirm_engagement`, and `wizard_retry_engagement`.
- Make Step 1 wait for target resolution when Telegram link intake returns a `pending` target so the
  wizard creates the draft engagement only after the target reaches `resolved` or `approved`.
- Add a bot API client regression test covering the wizard submission route sequence against a
  client configured with `base_url=.../api`.

## Validation

- `python scripts/check_fragmentation.py`
- `ruff check .`
- targeted wizard/client pytest coverage
- `pytest -q`
