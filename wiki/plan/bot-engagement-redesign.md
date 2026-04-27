# Bot Engagement Redesign Plan

## Goal

Refine the Telegram-bot-exclusive engagement operator surface so it feels guided, intention-first,
and aligned with the current `tg-outreach` implementation.

The redesign must reflect the actual codebase:

- approved engagement targets gate collection, join, detect, and send
- topics define what conversations matter
- prompt profiles and style rules shape runtime reply generation
- `engagement.detect` creates runtime-generated reply opportunities
- operators review `suggested_reply`, may edit `final_reply`, then approve/send
- all public replies remain audited through `engagement_actions`

This is not a plan for a parallel web cockpit or a generic campaign object.

## Product Direction

The operator experience should be organized around four recurring jobs:

1. Review pending reply opportunities
2. Resolve blockers and readiness gaps
3. Adjust the configuration that shapes future opportunities
4. Send approved replies safely

The redesign should make those jobs obvious from the first `/engagement` screen.

## Current Context

Already implemented:

- top-level inline operator cockpit
- Telegram-native engagement daily review and admin surfaces
- target approval and permission controls
- settings lookup and compact settings cards
- prompt profile, topic example, and style-rule creation/edit flows
- candidate review, edit, approve, reject, expire, retry, and send flows
- backend capability boundary for admin-only mutations

Current problem:

- the bot surface is functionally rich, but still reads too much like an admin console
- the home engagement surface can better prioritize operator intent and pending work
- reply opportunity review, readiness, and configuration controls need a cleaner split
- the runtime-generated reply model is now documented, but the UI flow should express it more clearly

## Non-Goals

- no web frontend as the primary operator surface
- no new campaign or engagement-run object that bypasses current target/topic/candidate models
- no auto-send workflow in MVP
- no weakening of `reply_only=true` and `require_approval=true`

## Slice 1: Home And Mode Hierarchy

Purpose:

Reshape `/engagement` into a clearer operator home.

Work items:

- make `Pending approvals` the first section when non-empty
- separate `Needs attention` from `Ready to review`
- keep admin/config entrypoints visible but secondary
- make the daily operator path read as `review -> approve/edit -> send`
- revise labels so default cards prefer operator language over backend nouns

Acceptance:

- `/engagement` immediately tells the operator what needs action
- pending reply opportunities are easier to distinguish from configuration pages
- admin controls are still reachable without dominating the first screen

## Slice 2: Reply Opportunity Queue Refinement

Purpose:

Make the reply-opportunity list feel like a guided queue instead of a raw candidate browser.

Work items:

- prioritize by approval urgency, freshness, and readiness
- expose stronger filters for `needs_review`, `approved`, `failed`, `expired`, and `sent`
- surface review and reply deadlines more prominently
- show why an opportunity exists in plain language before exposing lower-level fields
- standardize compact card anatomy across list and detail surfaces

Acceptance:

- the operator can scan the queue and decide what to review next quickly
- expired or stale opportunities are obviously different from fresh ones
- the reason to engage is clearer than the backend metadata

## Slice 3: Candidate Detail As Review Workspace

Purpose:

Turn candidate detail into a summary-first review workspace for one reply opportunity.

Work items:

- lead with source context, topic, generated suggestion, and current review state
- clearly separate `suggested_reply` from `final_reply`
- show approval/send readiness before secondary metadata
- make edit, approve, reject, expire, retry, and send actions feel like a coherent sequence
- keep diagnostic/provenance fields available lower in the card or in follow-up views

Acceptance:

- operators understand what the generated reply is responding to
- operators understand whether they are approving the generated suggestion or an edited final reply
- send readiness is obvious before the operator triggers a send

## Slice 4: Readiness And Blocker Surfaces

Purpose:

Expose why a reply opportunity or community is blocked without making the operator hunt through
settings, target, or action history cards.

Work items:

- summarize missing approval, posting disabled, no joined membership, stale deadline, or rate-limit blocks
- make settings lookup and target detail entrypoints easy from blocked candidate surfaces
- standardize readiness wording across formatting helpers
- ensure action failures explain what the operator should do next

Acceptance:

- blocked sends explain the actual next action
- operators can jump from a blocked opportunity to the right fix surface in one step

## Slice 5: Configuration Surfaces By Intent

Purpose:

Keep the admin/config surfaces powerful, but organize them by operator intent instead of backend table type.

Work items:

- group topic, prompt-profile, style-rule, and settings surfaces by what they influence
- make it obvious which controls shape future detection vs future reply wording vs send safety
- keep destructive or risky changes behind confirmation
- preserve current capability gating and callback namespaces

Acceptance:

- admins can tell whether they are changing target permissions, runtime drafting behavior, or send posture
- daily reviewers do not need to traverse admin-heavy screens for ordinary work

## Slice 6: Copy And Formatting Consistency

Purpose:

Make the engagement surface read consistently as a Telegram-native review tool.

Work items:

- prefer `reply opportunity` over `candidate` in operator-facing copy
- prefer `generated suggestion` and `final reply` over ambiguous `message` wording
- keep `candidate` only where implementation naming leaks through IDs or legacy command names
- standardize card summaries, headings, and button labels across engagement screens

Acceptance:

- the operator sees one coherent vocabulary across home, list, detail, edit, and send flows
- docs, formatting, and bot UI stop implying a prewritten-message workflow

## Slice 7: Release And Verification

Purpose:

Ship the redesign in small bot-safe slices with matching docs.

Work items:

- update affected spec shards as implementation lands
- append `wiki/log.md` per completed slice
- keep callback-data size, formatting length, and access-control tests current
- run `python3 scripts/check_fragmentation.py`
- run `ruff` and `pytest` when the repo environment has those modules available

Acceptance:

- wiki and shipped behavior stay aligned
- each slice lands as a focused commit

## Dependencies And Risks

- `bot/formatting_engagement.py` and `bot/ui_engagement.py` are likely pressure points for file-size growth
- candidate/detail/review flows span formatting, callback parsing, handlers, and API client methods
- wording changes must preserve audit clarity and not hide IDs where operators/admins still need them
- Telegram message length and callback-data limits remain hard constraints

## Suggested Build Order

1. Slice 1: Home And Mode Hierarchy
2. Slice 2: Reply Opportunity Queue Refinement
3. Slice 3: Candidate Detail As Review Workspace
4. Slice 4: Readiness And Blocker Surfaces
5. Slice 6: Copy And Formatting Consistency
6. Slice 5: Configuration Surfaces By Intent
7. Slice 7: Release And Verification
