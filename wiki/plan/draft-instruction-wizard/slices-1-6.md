# Draft Instruction Wizard Plan - Slices 1-6

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
