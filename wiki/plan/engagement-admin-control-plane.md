# Engagement Admin Control Plane Plan

## Goal

Implement the design in `wiki/spec/engagement-admin-control-plane.md`: manual engagement target
intake, separated core-vs-engagement controls, admin-editable prompt profiles, topic examples,
style rules, and editable candidate replies before send.

## Current Context

Already available:

- Engagement settings, topics, candidates, actions, joins, detection, send worker, and audit rows.
- Basic Telegram bot engagement cockpit, topic listing/creation/toggle, candidate approval, and
  explicit send queueing.
- Human approval and reply-only sending remain enforced.

Needed changes:

- Engagement-specific target intake instead of using regular seed add/import.
- Admin prompt profile storage and bot controls.
- Per-topic good/bad example management beyond the first create command.
- Per-scope style rules.
- Editable candidate final replies with revision history.
- Stronger separation between core app controls and engagement admin controls.

## Slice 1: Spec And Planning

Status: completed.

Add this plan and the new control-plane spec. Link both from `wiki/index.md` and record the design
change in `wiki/log.md`.

Acceptance:

- New spec covers target intake, prompt profiles, style rules, examples, editable replies, API, bot
  UX, audit, and testing.
- Existing engagement spec points readers to the control-plane spec.

## Slice 2: Engagement Targets Schema And Services

Status: planned.

Add `engagement_targets` and service methods for:

- create target from existing community ID or Telegram reference
- resolve target through engagement-specific queue job
- approve/reject/archive target
- enforce target approval before join, detect, and send

Acceptance:

- Regular seed add/import does not create engagement targets.
- Engagement jobs skip or fail closed when the target is missing or not approved.
- Tests cover existing-community intake, username/link intake, duplicate target handling, and
  seed/engagement separation.

## Slice 3: Prompt Profiles

Status: planned.

Add prompt profile and prompt profile version tables, service methods, and API endpoints.

Include:

- create, list, get, patch, activate, duplicate, and rollback
- model, temperature, max output tokens, system prompt, and user prompt template fields
- render-only preview endpoint
- deterministic active profile selection

Acceptance:

- Each prompt edit creates an immutable version row.
- Only one profile is active unless a later per-community override is implemented.
- Rendered previews include allowed variables only.
- Safety validation remains outside editable prompts.

## Slice 4: Prompt Assembly Refactor

Status: planned.

Refactor `engagement.detect` so it builds model input from:

- immutable safety floor
- active prompt profile
- global/account/community/topic style rules
- topic guidance and examples
- compact public message samples
- community-level analysis context

Acceptance:

- Existing detection tests still pass after adapting to prompt profiles.
- New tests prove sender identity, phone numbers, and private metadata do not enter prompt input.
- Candidate rows store prompt profile and version IDs.

## Slice 5: Topic Examples And Style Rules

Status: planned.

Add bot/API controls for:

- adding and removing good reply examples
- adding and removing bad reply examples
- style rule list/create/update/toggle by global, account, community, and topic scope

Acceptance:

- Good examples are passed as positive examples.
- Bad examples are passed as negative examples only.
- Style-rule precedence is stable and covered by tests.
- Unsafe style rules are rejected by backend validation.

## Slice 6: Editable Replies

Status: planned.

Add candidate edit support:

- `engagement_candidate_revisions`
- `/edit_reply <candidate_id> | <new final reply>`
- API endpoint for edit
- candidate cards that show suggested reply and current final reply
- approval of the latest valid final reply

Acceptance:

- Every edit creates a revision row.
- Edits run the same safety/length validation as generated replies.
- Approval uses `final_reply`, falling back to `suggested_reply` only when no edit exists.
- Send worker sends exactly the approved final text.

## Slice 7: Bot Control Separation

Status: planned.

Split the bot UX into daily engagement review and admin configuration.

Add:

- `/engagement_admin`
- target management cards
- prompt profile cards
- render preview cards
- style rule cards
- admin permission checks for prompt/style/target approval changes

Acceptance:

- Core app menus do not expose prompt or send controls.
- Engagement admin controls require admin operator permission.
- Long prompt edits use a safe conversation-state flow or explicit command syntax.
- Callback data stays within Telegram's 64-byte limit.

## Slice 8: Documentation, Tests, And Release

Status: planned.

Update after implementation:

- `wiki/spec/engagement.md`
- `wiki/spec/api.md`
- `wiki/spec/bot.md`
- `wiki/spec/database.md`
- `wiki/log.md`

Run focused Python tests and the repo's standard test command.

Acceptance:

- Bot, API, service, worker, and migration tests pass.
- Wiki index links any new specs/plans.
- Changes are committed and pushed when a remote is configured.

## Open Questions

- Should prompt profiles be assignable per community in the first implementation?
- Should approving an engagement target automatically create default engagement settings?
- Should full prompt editing be Telegram-only, or should the web frontend own long-form editing?
- Should full rendered prompts be stored always, or only under a debug flag?
- Should topic examples remain arrays, or become their own table before bot editing ships?
