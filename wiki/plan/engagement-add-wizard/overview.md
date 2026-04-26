# Engagement Add Wizard Plan Overview

Goal, context, UX principles, wizard model, references, open questions, and validation.

## Goal

Replace the current scattered engagement setup (target approval, per-action permissions, account
assignment, mode preset, topic management, and several MVP-locked flags) with one guided wizard
that walks a non-technical operator from "I want to engage in this community" to a running
detection job.

## Why

- The detection worker silently checks six independent gates
  (`backend/workers/engagement_detect_process.py:19-85`). A new operator hits a chain of
  "nothing is happening" outcomes with no single explanation.
- Several toggles are MVP-locked or auto-derivable from a single Level choice. Exposing them adds
  cognitive load without giving the operator real flexibility. Detail in
  `wiki/plan/engagement-add-wizard/collapse.md`.
- Topic creation already has a one-question-at-a-time flow
  (`wiki/plan/topic-create-question-flow.md`). The same UX principle should apply to the surrounding
  engagement setup.

## Scope

- A single resumable wizard launched from the engagement cockpit's "Add engagement" entry point.
- Five steps, each mapped to one real worker gate: community, topic(s), account, level, launch.
- Pick-or-create behavior at every step where reuse is possible (topics, accounts).
- Hidden defaults for MVP-locked toggles (`reply_only`, `require_approval`) and per-action target
  permission flags.
- Settings beyond the essentials (cadence, quiet hours, voice rules, prompt profiles) live in the
  cockpit's settings or library tabs, not the wizard.

## Non-Goals

- No new conversation framework. Reuse the pending-edit store used by the topic create flow.
- No new "draft" model. Partial wizard state lives on real engagement target rows in pre-`APPROVED`
  status, with topics and account assignments attached as the operator advances.
- No exposure of `engagement_targets.status`, per-action permission flags, MVP-locked settings,
  voice rules, or prompt profiles inside the wizard.
- No change to MVP send-approval semantics. Sends still require human approval.
- No automatic retry policy beyond what the existing workers already provide.

## UX Principles

- One question at a time. No multi-field forms.
- Each "Continue" button is gated on the real precondition. The wizard cannot reach Launch with a
  broken setup.
- When only one valid option exists (e.g. exactly one ENGAGEMENT-pool account), auto-pick and skip
  the choice screen.
- When the operator drops out, re-entering the wizard reads current state and resumes at the first
  incomplete step.
- The wizard hides internal terminology (`status`, `permissions`, `mode`, `target`). Operator-facing
  vocabulary is community, topic, account, and level.

## Wizard Model

The wizard routes over four pickable resources and a launch confirmation:

```text
Community  ->  Topic(s)  ->  Account  ->  Level  ->  Launch
```

Each step's full contract (prompt, internal effect, success gate, skip rules, failure modes) is in
`wiki/plan/engagement-add-wizard/steps.md`.

The redundant or MVP-locked controls hidden, derived, or removed by the wizard, plus the migration
notes for collapsing them in code, are in `wiki/plan/engagement-add-wizard/collapse.md`.

## References

- `wiki/spec/engagement.md` and `wiki/spec/engagement/lifecycle.md` for backend gate semantics.
- `wiki/plan/engagement-operator-controls/surface.md` for the existing operator command surface and
  preset table.
- `wiki/plan/topic-create-question-flow.md` for the precedent question-flow UX.
- `backend/workers/engagement_detect_process.py:19-85` for the canonical worker preconditions.
- `backend/services/community_engagement_settings.py:288-329` for the MVP-locked flags currently
  enforced server-side.

## Resolved Decisions

- Step 3 supports inline account creation. Phone-verification UX runs as a sub-flow inside the
  wizard, mirroring how Step 2 embeds topic create. Bouncing the operator to the accounts cockpit
  breaks setup momentum.
- Re-entering the wizard for a community already at `APPROVED` jumps straight to that community's
  cockpit. Per-field edits live in cockpit settings; the wizard's job ends at first launch.
- Launch hands off to the cockpit immediately with a "Started ✓" confirmation. The wizard does
  not wait on the first detect job; the cockpit is the live status surface.

## Validation

- Bot conversation tests for each step, including resume from partial state, pick-or-create
  branches, and gate-failure messages.
- Service-level tests for the auto-resolve, auto-approve, and auto-attach flows the wizard triggers
  on behalf of the operator.
- A test asserting the wizard's Level selection maps deterministically to the documented engagement
  mode plus derived per-action flags.
- `python scripts/check_fragmentation.py`.
- `ruff check .`.
- `pytest -q`.
