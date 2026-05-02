# Draft Instruction Wizard Plan

## Goal

Implement a guided drafting sub-flow inside `Add engagement` topic creation for teaching the
drafter what good public replies look like, using existing engagement topic, style-rule, and
example fields before introducing new storage.

The wizard should let operators express intent in normal language and examples instead of editing a
large raw prompt.

## Current Context

Already available:

- engagement topics with `description`, `stance_guidance`, keyword fields, and good/bad reply
  examples
- scoped style rules for global, account, community, and topic voice constraints
- prompt profiles and preview infrastructure
- Telegram conversation-state editing for long-form admin inputs
- candidate review with editable `final_reply`

Current gap:

- the system has the right low-level controls, but operators still need a guided path inside `Add
  engagement` topic creation instead of having to understand prompt/profile, topic, and style
  surfaces separately to improve draft quality
- there is no guided workflow that converts operator examples into durable instruction data
- learning from reply edits is manual and fragmented

## Locked Default Assumptions

Unless a later slice changes them explicitly, implementation should assume:

- the primary entry point is `Add engagement` -> Step 2 -> `Create topic`
- ordinary topic editing may reuse the same flow, but candidate review does not launch the full
  wizard in the first slice
- voice and avoid guidance auto-save into one topic-scoped style rule named
  `Draft instruction wizard`
- zero-example setup is allowed in the first slice
- example sets deduplicate case-insensitively where practical, but the first slice does not depend
  on a separate hard Telegram count cap
- preview defaults to a synthetic sample post and offers a real-post path when collected candidate
  context is available

## Slice 1: Spec And Wiring

Status: completed.

Add the draft-instruction wizard spec and this plan. Link both from `wiki/index.md` and record the
change in `wiki/log.md`.

Acceptance:

- the spec defines wizard steps, field mapping, preview, safety, and testing
- the plan stages implementation without forcing schema changes

## Slice 2: Bot Entry Point And State Machine

Status: completed.

Add the embedded topic-creation drafting entry point under `Add engagement` Step 2 for all
bot-authorized operators and Telegram conversation state for:

- selecting or creating a topic
- collecting conversation target
- collecting reply position
- collecting voice/style guidance
- collecting good reply examples
- collecting bad reply examples
- collecting optional avoid rules

Acceptance:

- each step has explicit next, back, skip-when-allowed, save-later, and cancel behavior
- state is scoped to the operator and expires similarly to other long-form edit flows
- the bot uses operator-facing labels rather than backend field names

## Slice 3: Preview And Save

Status: completed.

Add a `Draft brief` preview card that summarizes the assembled instruction before save.

Save should call existing topic/style/example APIs instead of introducing a parallel persistence
path.

Acceptance:

- preview shows conversation target, reply position, voice, good examples, and avoid guidance
- save creates or updates topic fields and examples through existing service validation
- voice guidance is persisted through a visible style rule

## Slice 4: Test Preview Against A Post

Status: completed.

Allow admins to test the current wizard inputs against a real or synthetic source post before
saving.

Acceptance:

- preview reuses existing prompt-preview infrastructure where practical
- generated output is clearly labeled as a draft preview
- preview never hits approval or send endpoints

Implementation note:

- the current shipped path uses a synthetic sample post; a real-post picker is still an optional
  follow-up rather than a missing slice blocker

## Slice 5: Review-To-Learning Shortcuts

Status: completed.

Add follow-up actions from candidate review so operators can turn a strong manual edit into future
guidance.

Include:

- save edited `final_reply` as a good example
- create a style rule from an edit

Acceptance:

- shortcuts are explicit operator actions, never automatic learning
- saved examples land in the selected topic example set
- style-rule creation asks for the intended scope

Implementation note:

- the current shortcut can save or derive guidance from the current reply text, which may be
  `final_reply` or the unedited suggestion when no final edit exists yet

## Slice 6: Safety, Copy, And Guardrails

Status: completed.

Add backend and bot guardrails so the wizard cannot be used to smuggle unsafe instruction changes
through a friendlier UI.

Acceptance:

- unsafe examples and style guidance are rejected consistently with existing validation
- bad examples are passed as negative examples only
- preview respects prompt-size caps and privacy boundaries
- wizard copy makes clear that examples teach shape, not literal templates

## Slice 7: Tests And Release

Status: completed.

Add focused tests and ship in bot-safe slices.

Minimum verification:

- bot state-machine tests for the wizard flow
- formatting tests for `Draft brief` previews
- API/client tests for wizard-used mutations
- safety tests for example handling and preview isolation
- `python scripts/check_fragmentation.py`
- `ruff check .`
- `pytest -q`

## Slice 8: Example Loop Refinement

Status: completed.

Add Telegram-native repeated add-another loops for good and bad examples so operators can build up
example sets incrementally instead of having to paste all examples in one message.

Acceptance:

- good-example and bad-example steps allow `add another`, `continue`, and `done reviewing examples`
- preview reflects examples accumulated across multiple loop turns
- existing blank-line multi-example entry remains supported for fast paste workflows
- back, skip, save-later, and cancel still behave predictably inside the loop states

Implementation note:

- the shipped flow accumulates examples across repeated Telegram turns, deduplicates repeated
  entries case-insensitively inside the in-flight wizard state, and keeps `-` as a no-new-example
  advance path once at least one example has already been collected for that step

## Slice 9: Real-Post Preview

Status: completed.

Extend draft-brief testing so admins can preview the current instructions against a real collected
post in addition to the existing synthetic sample preview.

Acceptance:

- operators can choose between synthetic sample preview and real-post preview
- the real-post path uses an existing collected post or candidate context rather than inventing new
  persistence
- generated output remains clearly labeled as draft preview only
- the preview path never calls approval or send endpoints

Implementation note:

- the bot now offers `Test sample` and `Test real post` from the draft-brief confirmation screen
- the real-post path reuses existing candidate context scoped to the current community or topic
  when available
- when no collected candidate context exists yet, the bot keeps the draft in place and explains how
  to recover with sample preview or later collection

## Slice 10: Wizard Style-Rule Scope Choice

Status: completed.

Let operators choose where wizard-owned voice and avoid guidance should be saved instead of always
creating or updating a topic-scoped `Draft instruction wizard` style rule.

Acceptance:

- the wizard can save guidance at topic scope and, when relevant context exists, offer community or
  existing-rule attachment choices
- the saved rule remains visible and editable through normal style-rule surfaces
- the choice is explicit at preview/save time rather than hidden in backend defaults
- no parallel persistence path is introduced

Implementation note:

- the confirmation screen now shows the current guidance save target, keeps topic scope as the
  default, offers community scope when the draft was launched from `Add engagement`, and can attach
  the guidance to an existing topic/community rule instead of always creating a new wizard-owned
  rule

## Slice 11: Edited-Reply-Only Learning Alignment

Status: completed.

Tighten the candidate-review learning shortcuts so they apply only to deliberate manual reply edits
when the product decision is to align strictly with the current spec wording.

Acceptance:

- `Save as good example` and `Create style rule from this edit` require an edited `final_reply`
  rather than falling back to `suggested_reply`
- candidate detail copy makes the requirement clear when no edited reply exists yet
- tests cover both the available and unavailable states for these shortcuts
- if product decides to keep the broader current behavior, close this slice by updating the spec
  instead of changing the bot

Implementation note:

- candidate-review learning shortcuts now stay hidden until an operator edits `final_reply`, both
  shortcut callbacks reject fallback-to-`suggested_reply`, and candidate detail copy explains that
  the learning actions unlock only after a deliberate final-reply edit

## Suggested Build Order

1. Slice 2: Bot Entry Point And State Machine
2. Slice 3: Preview And Save
3. Slice 6: Safety, Copy, And Guardrails
4. Slice 4: Test Preview Against A Post
5. Slice 5: Review-To-Learning Shortcuts
6. Slice 7: Tests And Release
7. Slice 8: Example Loop Refinement
8. Slice 9: Real-Post Preview
9. Slice 10: Wizard Style-Rule Scope Choice
10. Slice 11: Edited-Reply-Only Learning Alignment

## Deferred Follow-Ups

- Should real-post preview eventually grow from a best-available candidate lookup into an explicit
  picker for choosing among multiple collected posts?
- Should wizard-owned guidance keep the default topic scope, or offer scope choice more broadly?
- Should candidate-review shortcuts stay lightweight, or ever launch the full wizard directly?
