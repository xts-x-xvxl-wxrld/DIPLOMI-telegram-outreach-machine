# Developer Docs

Developer-facing documentary pages for this repository.

Use this lane for verified understanding of live code:
- how a subsystem is organized
- where important flows start and branch
- what invariants, seams, and footguns matter during edits

Do not use this lane for operator instructions or to restate the full behavior specs.

## Read First

- [Protocol](protocol.md) - maintenance rules and evidence standard
- [Glossary](glossary.md) - stable project vocabulary for developer docs
- [Module Guide Template](templates/module-guide.md) - starter structure for subsystem pages
- [Flow Guide Template](templates/flow-guide.md) - starter structure for runtime-path pages

## Planned Families

- `architecture/` - subsystem maps and cross-cutting boundaries
- `modules/` - ownership and entrypoint guides for specific code areas
- `flows/` - step-by-step execution paths
- `patterns/` - recurring conventions, seams, and extension points

## Module Guides

- [Engagement Approval Notifications](modules/engagement-approval-notifications.md) - bot startup,
  queue scan, and per-operator dedupe seams for proactive approval-draft alerts
- [Engagement Approval Review](modules/engagement-approval-review.md) - task-first approval queue
  payload shaping and Telegram draft-card formatting seam
- [Engagement Detect Continuations](modules/engagement-detect-continuations.md) - direct-reply
  continuation selection that keeps approved Telegram threads draftable without repeated trigger
  keywords
- [Engagement Prompt Profiles](modules/engagement-prompt-profiles.md) - active-vs-fallback draft
  instruction selection, preview alignment, and prompt-template ownership
- [Engagement Quiet Hours](modules/engagement-quiet-hours.md) - quiet-hours timezone
  storage, runtime evaluation, and wizard/cockpit edit seam
- [Engagement Wizard Confirm Handoff](modules/engagement-wizard-confirm-handoff.md) - success
  reply plus backend callback reroute seam after task-first wizard confirm
- [Engagement Wizard Cancel Home](modules/engagement-wizard-cancel-home.md) - confirmed
  wizard cancel reroute back to the shared `Engagements` cockpit home
- [Bot Search Temporary Removal](modules/bot-search-temporary-removal.md) - bot-side kill switch, Discovery copy changes, and stale search-callback blocking
- [Engagement Topic Brief State](modules/engagement-topic-brief-state.md) - bot-side `topic_create`
  pending-edit recovery, snapshot cleanup, and stale-callback seam

## Relationship To Other Wiki Lanes

- `wiki/spec/` says what the system should do.
- `wiki/code-index/` helps you find where code lives.
- `wiki/dev-docs/` explains how the currently inspected code is wired and what developers should
  know before changing it.
