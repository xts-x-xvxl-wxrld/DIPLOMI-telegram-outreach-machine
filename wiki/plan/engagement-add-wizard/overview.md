# Engagement Add Wizard Plan Overview

Goal, context, UX principles, wizard model, references, open questions, and
validation.

## Goal

Replace scattered engagement setup with one guided wizard that walks a
non-technical operator from "I want to engage in this community" to a running
engagement.

## Why

- The detection worker silently checks six independent gates
  (`backend/workers/engagement_detect_process.py:19-85`). A new operator hits a chain of
  "nothing is happening" outcomes with no single explanation.
- Several toggles are MVP-locked or auto-derivable from a single sending-mode
  choice. Exposing them adds cognitive load without giving the operator real
  flexibility. Detail in
  `wiki/plan/engagement-add-wizard/collapse.md`.
- Topic creation already has a one-question-at-a-time flow
  (`wiki/plan/topic-create-question-flow.md`). The same UX principle should apply to the surrounding
  engagement setup.

## Scope

- A single wizard launched from the engagement cockpit's `Add engagement`
  entry point.
- Five steps: target, topic, account, sending mode, final review.
- Pick-or-create behavior at every step where reuse is possible (topics, accounts).
- Hidden defaults for MVP-locked toggles (`reply_only`, `require_approval`) and per-action target
  permission flags.
- Settings beyond the essentials (cadence, quiet hours, voice rules, prompt profiles) live in the
  cockpit's settings or library tabs, not the wizard.

## Non-Goals

- No new conversation framework. Reuse the pending-edit store used by the topic create flow.
- No detect-only mode in the wizard.
- No UI resume-from-abandoned-setup behavior.
- No exposure of `engagement_targets.status`, per-action permission flags, MVP-locked settings,
  voice rules, or prompt profiles inside the wizard.

## UX Principles

- One question at a time. No multi-field forms.
- Each step is gated on the real precondition.
- When only one valid option exists (e.g. exactly one ENGAGEMENT-pool account), auto-pick and skip
  the choice screen.
- When the operator drops out, starting again begins from Step 1.
- The wizard hides internal terminology (`status`, `permissions`, `mode`, `target`). Operator-facing
  vocabulary is target, topic, account, and sending mode.

## Wizard Model

The wizard routes over four pickable resources and a final review:

```text
Target  ->  Topic  ->  Account  ->  Sending mode  ->  Final review
```

Each step's full contract (prompt, internal effect, success gate, skip rules, failure modes) is in
`wiki/plan/engagement-add-wizard/steps.md`.

The redundant or MVP-locked controls hidden, derived, or removed by the wizard, plus the migration
notes for collapsing them in code, are in `wiki/plan/engagement-add-wizard/collapse.md`.

## References

- `wiki/spec/engagement.md` and `wiki/spec/engagement/lifecycle.md` for backend gate semantics.
- `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md` for the current operator
  cockpit surface.
- `wiki/plan/topic-create-question-flow.md` for the precedent question-flow UX.
- `backend/workers/engagement_detect_process.py:19-85` for the canonical worker preconditions.
- `backend/services/community_engagement_settings.py:288-329` for the MVP-locked flags currently
  enforced server-side.

## Resolved Decisions

- Step 3 supports inline account creation. Phone-verification UX runs as a sub-flow inside the
  wizard, mirroring how Step 2 embeds topic create. Bouncing the operator to the accounts cockpit
  breaks setup momentum.
- Re-entering from `Add engagement` starts fresh; abandoned setup is not
  surfaced or resumed.
- Editing an existing engagement reopens the full wizard at the tapped step with
  prefilled values.
- Final review hands off to the engagement detail flow immediately after confirm.

## Validation

- Bot conversation tests for each step, including fresh-start behavior,
  pick-or-create branches, and gate-failure messages.
- Service-level tests for the auto-resolve, auto-approve, and auto-attach flows the wizard triggers
  on behalf of the operator.
- A test asserting the wizard's sending-mode selection maps deterministically to
  the documented engagement mode plus derived per-action flags.
- `python scripts/check_fragmentation.py`.
- `ruff check .`.
- `pytest -q`.
