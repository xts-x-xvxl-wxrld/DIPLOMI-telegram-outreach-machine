# Task-First Engagement Settings Exposure

## Goal

Make task-first engagement setup match runtime behavior by:

- exposing task-first cadence settings instead of keeping them hidden behind
  defaults and worker enforcement
- changing the active default cadence from `1 post / 240 minutes` to
  `300 posts / 1 minute`
- exposing quiet hours during engagement setup so operators can review and
  change them before confirming, including the timezone the quiet window is
  evaluated in

## Scope

- `PUT /api/engagements/{engagement_id}/settings`
- task-first engagement settings DTOs and service validation
- engagement settings model defaults and migration backfill
- bot task-first API client
- engagement wizard review/edit flow for quiet hours
- quiet-hours timezone storage plus wizard/cockpit selection controls
- focused route, bot-client, and wizard tests

## Constraints

- keep `reply_only = true` and `require_approval = true`
- keep task-first sending mode choices limited to `suggest` and
  `auto_limited`
- do not introduce a second quiet-hours editing workflow just for setup if
  existing parsing/save behavior can be reused cleanly
- preserve the active wizard wording refresh that is already in progress in
  the worktree

## Plan

1. Expand the task-first settings request/response contract to include
   `max_posts_per_day` and `min_minutes_between_posts`.
2. Raise the task-first and shared engagement defaults to `300` and `1`,
   update validation, and add a migration that updates rows still carrying the
   old default values.
3. Store cadence and quiet-hours values in wizard state, surface them on the
   review card, and add a setup-time quiet-hours edit action with `HH:MM-HH:MM`
   or `off` input.
4. Persist a quiet-hours timezone alongside the window, keep legacy rows on
   `utc`, and expose the operator choices as `CET`, `US East`, and `US West`.
5. Update the engagement API, bot client, and wizard tests to cover the new
   contract and setup flow.
