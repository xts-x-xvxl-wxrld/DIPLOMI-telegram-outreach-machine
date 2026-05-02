# Draft Instruction Wizard Plan - Slices 7-11

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
