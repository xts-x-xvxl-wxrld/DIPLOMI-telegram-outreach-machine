# Draft Instruction Wizard

Wizard contract for teaching engagement drafting behavior through guided operator questions instead
of raw prompt editing.

## Responsibility

The draft instruction wizard should help bot-authorized operators express what good reply drafting looks
like without requiring prompt-engineering knowledge. It turns operator answers into existing topic,
style-rule, and example fields, then shows a compact preview before save.

This wizard is not a separate top-level setup destination. The source-of-truth product decision is
that drafting and prompt-targeted operator changes should be handled inside the `Add engagement`
wizard when the operator chooses `Create topic` from Step 2.

This wizard shapes future detection and draft creation, but it does not send replies, bypass
approval, or replace the existing prompt-profile model.

## Product Direction

The wizard should ask normal human questions about reply quality, not backend-configuration names.
It should feel like teaching a reviewer or drafter:

- what conversations matter
- what useful contribution the reply should make
- how the reply should sound
- what a good reply looks like
- what a bad reply looks like
- what the reply must avoid

The first implementation should reuse existing stored fields where possible. The goal is to improve
instruction quality and consistency before introducing a new schema object.

## Default Assumptions

The first implementation should treat the following defaults as locked unless a later slice changes
 them explicitly:

- the primary entry point is `Add engagement` -> Step 2 -> `Create topic`
- ordinary topic editing may reuse the same flow, but candidate review does not launch the full
  wizard in the first slice
- saving voice and avoid guidance automatically creates or updates one topic-scoped wizard-owned
  style rule named `Draft instruction wizard`
- zero-example setup is allowed in the first slice; good examples are encouraged but not required
- good and bad examples should deduplicate case-insensitively where practical, but the first slice
  does not require a separate hard Telegram count cap beyond existing prompt-size and message-size
  guardrails
- the preview defaults to a synthetic sample post and offers a real-post path when collected
  candidate context is available

## Wizard Inputs

The wizard should collect the following operator-facing steps.

| Step | Operator question | Primary destination |
|---|---|---|
| Conversation target | What kind of discussion should we notice? | `topic.description`, optional `trigger_keywords`, optional `negative_keywords` |
| Reply position | What should our reply contribute? | `topic.stance_guidance` |
| Voice and constraints | How should this account sound here? | style rule `rule_text` at topic or community scope |
| Good replies | Paste replies you would be happy for the model to write. | `topic.example_good_replies` |
| Bad replies | Paste replies that are too salesy, risky, fake, or off-tone. | `topic.example_bad_replies` |
| Avoid rules | Anything the reply must never do? | style rule `rule_text` when stylistic, otherwise validation failure or warning |

The wizard should present examples as examples, not templates. Operator copy should explain:

```text
Good examples teach the shape of a helpful reply.
Bad examples teach what to avoid.
The model should not copy examples word for word.
```

## Field Mapping Rules

The first implementation should map wizard answers into the existing control-plane model.

### Topics

- `description` stores the conversation target in natural language.
- `stance_guidance` stores the desired contribution or position.
- `trigger_keywords` and `negative_keywords` may be optionally edited in advanced mode, but they
  should not be required to complete the wizard.
- `example_good_replies` and `example_bad_replies` remain the canonical storage for reply examples.

### Style rules

- Voice, brevity, disclosure posture, link posture, and community-tone constraints should be saved
  as style rules instead of prompt-profile text when they answer "how should this sound?"
- The preview/save screen should show where wizard-owned guidance will be saved.
- Topic scope remains the default save target and still uses the visible wizard-owned style rule
  named `Draft instruction wizard`.
- When the wizard has relevant engagement context, operators may switch that guidance to community
  scope or attach it to an existing topic/community rule instead of always using the default
  wizard-owned topic rule.
- Wizard-generated style rules remain fully visible and editable through normal style-rule surfaces.

### Prompt profiles

- The topic-creation branch inside `Add engagement` is the preferred operator surface for ordinary
  drafting changes.
- Prompt profiles remain responsible for model role, output schema, and stable drafting rubric.
- Direct prompt-profile editing may still exist as an advanced library/control-plane surface, but
  ordinary drafting changes should be captured through the Step 2 `Create topic` flow rather than a
  separate standalone prompt-editing workflow.

## Wizard Flow

Recommended Telegram bot flow inside `Add engagement` Step 2 `Create topic`:

```text
start Add engagement
  -> Step 2
  -> choose target topic or create topic
  -> if create topic:
  -> collect conversation target
  -> collect reply position
  -> collect voice/style guidance
  -> collect one or more good reply examples
  -> collect one or more bad reply examples
  -> collect optional avoid rules
  -> preview assembled brief
  -> save or revise one section
```

Rules:

- Each step should show the current draft value and allow skip only when the underlying field is
  optional.
- Good and bad reply steps should support repeated add-another loops before preview.
- The preview should be summary-first and should not expose backend field names by default.
- Save must write through the existing topic/style/example APIs so audit and validation stay in one
  place.
- Cancel must abandon the pending wizard state without mutating backend data.

## Preview Contract

Before save, the wizard should render a concise `Draft brief` preview:

```text
We will look for:
<conversation target>

We will contribute:
<reply position>

Voice:
<style guidance>

Good reply examples:
<1..n examples>

Avoid:
<bad examples and explicit avoid rules summary>

Guidance saves to:
<topic rule, community rule, or attached existing rule>
```

The preview should support two levels:

- brief preview: assembled human-readable instruction summary
- test preview: render the same instruction against a real or synthetic source post and show the
  resulting generated suggestion without saving

Test preview rules:

- it must call a render/preview path only, not send or approve paths
- it may reuse the existing prompt-preview infrastructure with synthetic candidate context
- it must clearly label generated output as a draft preview

## Learn From Edits

Candidate review should optionally feed future wizard inputs.

When an operator edits `final_reply`, the bot may offer follow-up actions such as:

```text
Save as good example
Create style rule from this edit
Dismiss
```

Rules:

- these follow-up actions are explicit operator choices, never automatic learning
- saving an edited reply as a good example should append to the selected topic examples API
- creating a style rule from an edit should require the operator to choose the scope
- these follow-up actions do not launch the full draft-instruction wizard in the first slice
- terminal sent candidates should not reopen ordinary edit flows, but their approved final text may
  still be referenced for manual example creation if a later slice adds that shortcut

## Validation And Safety

The wizard is an authoring aid, not a bypass around existing safety constraints.

Validation rules:

- topic guidance, style guidance, and example fields should accept operator input as-authored for
  research and drafting analysis, including exploratory or adversarial examples that would not be
  appropriate as final sent replies
- avoid rules may tighten behavior, but may not weaken hard product rules
- bad examples must be stored and passed as negative examples only
- good examples should be deduplicated case-insensitively within the same topic where practical
- the preview must remain bounded by the existing prompt-input size caps

The backend remains authoritative for:

- no DMs
- no fake consensus
- no impersonation or fake personal experience
- no auto-send
- no person-level targeting
- reply validation and approval requirements

Authoring note:

- accepting unrestricted operator input in the wizard does not imply the same text can be sent
  directly; send-time and model-behavior constraints still govern generated and approved replies

## API And Bot Dependencies

The first implementation should rely on existing or already planned admin routes:

- topic create/update/detail routes
- topic example create/remove routes
- style-rule create/update/list routes
- prompt preview route for synthetic or real sample rendering

If a one-shot wizard save endpoint is added later, it should be a convenience facade over the same
validated topic/style/example service methods, not a parallel persistence path.

Entry-point rule:

- the primary entry point for this flow is `Add engagement` -> Step 2 -> `Create topic`
- if later shortcuts launch the same flow from topic editing or candidate review, they should reuse
  the same underlying topic/style/example contract instead of creating a separate prompt-authoring
  source of truth

## Testing Contract

Minimum coverage for implementation:

- bot conversation-state tests for each wizard step, skip path, preview, save, and cancel
- formatting tests for the assembled `Draft brief` preview
- API/client tests for topic example and style-rule mutations used by the wizard
- safety tests proving bad examples remain negative examples only
- tests proving preview actions never call approval or send endpoints
- tests proving wizard-created instructions are visible in normal topic/style detail surfaces

## Audit Guidance

For final audit and release review, treat this as the primary readiness path:
`Add engagement` -> Step 2 -> `Create topic` -> complete `Draft brief` -> preview -> save ->
return to `Add engagement` with the new topic selected.

Final review should verify:

- the draft-instruction wizard is only launched as an embedded `Create topic` branch inside `Add
  engagement` for the primary operator path; no standalone top-level wizard is required
- topic create/edit writes still go through the existing topic/style/example APIs rather than a
  parallel wizard persistence path
- both `Test sample` and `Test real post` stay render-only and never call approval or send actions
- the operator can explicitly choose where voice/avoid guidance is saved when relevant engagement
  context exists: topic-scoped wizard rule, community-scoped wizard rule, or attachment to an
  existing topic/community rule
- after a successful topic save from the embedded flow, the operator returns to the parent `Add
  engagement` wizard with the new topic selected

Current implementation guidance:

- treat community-scope and existing-rule attachment as save-time choices that are guaranteed in
  the embedded `Add engagement` flow when engagement context is present
- later topic-only draft-brief edits may reuse the same question flow, but they should not be
  relied on to reconstruct prior community-scope or existing-rule attachment choices unless a later
  slice stores that relationship explicitly
- candidate-review learning shortcuts require an edited `final_reply`; generated suggestions alone
  are not enough to save a good example or derive a style rule from review
## Release Checklist
Use this as a yes/no launch rubric for the primary path.
- Yes/No: Can an operator start `Add engagement`, reach Step 2, choose `Create topic`, and enter
  the embedded draft-brief flow?
- Yes/No: Can the operator complete the required questions and use skip only on the optional ones?
- Yes/No: Do good/bad example steps support repeated add-another loops before confirmation?
- Yes/No: Do `Test sample` and `Test real post` stay preview-only and avoid approval/send actions?
- Yes/No: Does save persist through the existing topic/style/example APIs rather than a separate
  wizard persistence path?
- Yes/No: When engagement context exists, can the operator choose topic scope, community scope, or
  an existing rule for voice/avoid guidance?
- Yes/No: After save, does the flow return to `Add engagement` with the newly created topic
  selected?
- Yes/No: Are wizard-created instructions visible through the normal topic/style detail surfaces?
- Yes/No: Are bad examples still treated as negative examples only?
- Yes/No: Are candidate-review learning shortcuts treated as secondary behavior rather than part of
  the required primary launch path?
Release recommendation:
- recommend launch when all primary-path questions above are `Yes`
- treat topic-only re-entry not round-tripping prior non-topic save targets as a known non-blocking
  limitation unless product explicitly chooses to tighten it before release
## Launch Review
2026-05-01 primary-path rubric run:

- Yes: An operator can start `Add engagement`, reach Step 2, choose `Create topic`, and enter the
  embedded draft-brief flow.
- Yes: Required questions stay required, while only optional fields support skip.
- Yes: Good and bad example steps support repeated add-another loops before confirmation.
- Yes: `Test sample` and `Test real post` stay preview-only and do not hit approval/send actions.
- Yes: Save persists through the existing topic/style/example APIs rather than a separate wizard
  persistence path.
- Yes: When engagement context exists, the operator can choose topic scope, community scope, or an
  existing rule for voice/avoid guidance.
- Yes: After save, the embedded flow returns to `Add engagement` with the new topic selected.
- Yes: Wizard-created instructions remain visible through the normal topic/style detail surfaces.
- Yes: Bad examples remain negative examples only.
- Yes: Candidate-review learning shortcuts remain secondary behavior rather than part of the
  required primary launch path.

Launch call:

- Recommend launch for the primary embedded path.
- Keep the current topic-only re-entry save-target limitation tracked as a non-blocking follow-up
  unless product decides to tighten it before release.
## Deferred Follow-Ups
- broader guidance-target choices such as account/global scope or multi-rule save behavior beyond
  the current topic/community and existing-rule attachment paths
- launching the same flow directly from candidate review when operators notice repeated draft
  problems
