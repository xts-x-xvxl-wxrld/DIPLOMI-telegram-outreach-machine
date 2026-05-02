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
  engagement` topic creation instead of understanding prompt/profile, topic, and style surfaces
  separately to improve draft quality
- there is no guided workflow that converts operator examples into durable instruction data
- learning from reply edits is manual and fragmented

## Locked Default Assumptions

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

## Slice Shards

- [Slices 1-6](draft-instruction-wizard/slices-1-6.md) - spec/wiring, bot state, save path,
  preview, review-learning shortcuts, and safety guardrails
- [Slices 7-11](draft-instruction-wizard/slices-7-11.md) - tests/release, example-loop refinement,
  real-post preview, style-target choice, and edited-reply-only learning alignment

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
