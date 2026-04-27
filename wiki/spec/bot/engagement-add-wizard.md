# Engagement Add Wizard

Guided five-step setup wizard that walks an operator from a blank target to a
running engagement. Launched from the engagement cockpit's `Add engagement`
entry point.

`wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md` is the
active UX source of truth. This shard defines the wizard's implementation
contract under that UX.

## Purpose

Replace scattered engagement setup with one guided flow that gets a
non-technical operator from "I want to engage here" to a working engagement.

Backend model rule:

- an engagement is a first-class backend entity
- the wizard creates or reuses an `engagement` record, not just loose
  per-community settings
- the chosen topic, chosen account, and sending mode belong to that engagement

## Goals

- One question at a time. No multi-field forms.
- Use only operator-facing terms: target, topic, account, sending mode.
- Start from the beginning when abandoned setup is reopened.
- Reuse durable backend rows idempotently behind the scenes.
- Hide raw status machines, permission flags, and backend mode names.

## Non-Goals

- No detect-only mode in the wizard.
- No restore-from-abandoned-wizard UI.
- No exposure of `engagement_targets.status`, per-action flags, or MVP-locked
  settings.
- No change to the underlying approval and safety constraints unless called out
  below.

## Wizard Flow

```text
Target  ->  Topic  ->  Account  ->  Sending mode  ->  Final review
```

## Screen Layout Contract

Step 1 — Target

- title: `Add engagement`
- show `Step 1 of 5`
- prompt: `Which target?`
- helper line: `Paste @handle or t.me/... link`
- do not show a primary continue button before target resolution succeeds

Step 2 — Topic

- title: `Add engagement`
- show `Step 2 of 5`
- prompt: `Choose a topic or create a new one`
- show equal-weight actions:
  - `Choose topic`
  - `Create topic`
  - `Continue`
- enable `Continue` only after one topic is selected

Step 3 — Account

- title: `Add engagement`
- show `Step 3 of 5`
- prompt: `Which account should engage from?`
- render a plain list of engagement accounts plus `Add new account`
- selecting an account should trigger join work immediately and auto-advance on
  success

Step 4 — Sending mode

- title: `Add engagement`
- show `Step 4 of 5`
- prompt: `How should sending work?`
- options:
  - `Draft` — `Review each reply before send`
  - `Auto send` — `Send automatically with limits`
- show `Continue`
- preselect `Draft`

Step 5 — Final review

- title: `Add engagement`
- show `Step 5 of 5`
- render a read-only summary of target, topic, account, and sending mode
- actions:
  - `Confirm`
  - `Retry`
  - `Cancel`

## Step Contracts

### Step 1 — Target

- Prompt: `Which target? Paste @handle or t.me/... link.`
- Internal effect:
  resolve the target through existing engagement intake; if no target row
  exists, create one in `RESOLVED`, then create or reuse a draft engagement row
  tied to that target.
- Pick-or-create behavior:
  - target at `RESOLVED` or earlier: continue setup
  - target already at `APPROVED`: open that engagement instead of duplicating it
- Success gate:
  a durable engagement row exists for the chosen target.
- Failure modes:
  - resolution fails: show an operator-friendly reason and stop
  - invalid input: re-prompt without state changes

### Step 2 — Topic

- Prompt: `Choose a topic or create a new one.`
- Pick-or-create behavior:
  - choose an existing topic
  - create a new topic through the existing topic-create sub-flow, then return
    here with it preselected
- Internal effect:
  attach the chosen topic to the engagement. The launch summary shows only that
  topic for the engagement.
- Success gate:
  one topic is selected.
- Failure modes:
  - topic-create aborts: return here with no topic selected

### Step 3 — Account

- Prompt: `Which account should engage from?`
- Pick-or-create behavior:
  - choose an existing ENGAGEMENT-pool account from a plain list
  - add a new account through the existing onboarding sub-flow, then return here
    with it preselected
- Internal effect:
  1. set the engagement's assigned account
  2. trigger `community.join` for the chosen account
  3. stream join progress in the wizard message
- Success gate:
  a joined account membership exists for the target.
- Skip rules:
  - one engagement account only: auto-pick, still perform join
  - already joined: skip the join work and continue
- Failure modes:
  - account cannot join: offer another account or account create
  - FloodWait: show retry-after timing and allow retry in place
  - account-create aborts: return to the picker

### Step 4 — Sending Mode

- Prompt: `How should sending work?`
- Choices:
  - `Draft` *(default)* — create draft replies for operator approval
  - `Auto send` — allow capped automatic sends after setup
- Canonical internal mapping:
  - `Draft` → `engagement_settings.mode = suggest`
  - `Auto send` → `engagement_settings.mode = auto_limited`
- Derived flags:
  - `Draft` → `allow_detect=true`, `allow_post=false`
  - `Auto send` → `allow_detect=true`, `allow_post=true`
- Success gate:
  the engagement settings row records the chosen sending mode.
- Rules:
  - no detect-only option exists in the wizard
  - off/paused remains a cockpit setting, not a setup choice
- Implementation requirement:
  `Auto send` is an immediate feature, not a deferred one. The same delivery
  slice must remove the current MVP validation guard that rejects
  `auto_limited`.

### Step 5 — Final Review

- Prompt:
  read-only summary of target, topic, account, and sending mode.
- Actions:
  - `Confirm`
  - `Cancel`
  - `Retry`
- `Confirm` internal effect:
  1. enqueue the first `engagement.detect` job for the target
  2. only on enqueue acceptance, activate the engagement and flip the target to
     `APPROVED` when needed
  3. show a short started confirmation
  4. open the engagement detail flow
- Success gate:
  detect job accepted and target at `APPROVED`.
- Failure modes:
  - detect enqueue fails: stay on final review and show the queue error
- Behavior:
  - `Retry` restarts the wizard from Step 1
  - `Cancel` requires confirmation before discard

## Start-Again Behavior

- `Add engagement` always starts at Step 1.
- Abandoned or cancelled setup does not reopen where it left off.
- Any temporary wizard state is cleared on new entry.
- Durable rows created during a previous attempt may still be reused safely once
  the operator chooses the same target again.

## Editing Existing Engagements

- Tapping topic, account, or sending mode in engagement detail reopens the full
  wizard.
- Existing values are prefilled.
- The wizard opens on the tapped step.
- The operator can still go backward to earlier steps.

## Cancellation

- `/cancel_edit` remains active throughout the wizard.
- Cancel never promotes a target to `APPROVED`.
- Cancelled or incomplete setup does not surface on home.
- Partial backend rows may remain, but they are implementation detail, not user
  flow state.

## Wizard Write Contract

Treat the wizard as a staged write flow for one draft engagement.

Contract shape:

- use generic write endpoints for step-owned draft fields
- use semantic endpoints for workflow-edge actions
- do not make the bot orchestrate full wizard commit/reset through raw field
  patches alone

Write rules:

- Step 1 creates or reuses a draft `engagement` for the chosen target
- Step 2 writes exactly one `topic_id` onto that engagement
- Step 3 writes the assigned account and drives join work
- Step 4 writes the sending-mode-backed engagement settings
- Step 5 validates the full draft and activates it atomically

Commit rules:

- `Back` changes screen position only; it does not discard durable draft writes
- `Retry` clears wizard-owned draft choices and restarts at Step 1
- `Cancel` abandons the wizard flow without surfacing the incomplete engagement
  in normal lists
- `Confirm` is the only action that may activate the engagement

Endpoint split:

- generic writes:
  - `POST /api/engagements`
  - `PATCH /api/engagements/{engagement_id}`
  - `PUT /api/engagements/{engagement_id}/settings`
- semantic workflow edges:
  - `POST /api/engagements/{engagement_id}/wizard-confirm`
  - `POST /api/engagements/{engagement_id}/wizard-retry`

Edit-entry rules:

- reopening the wizard from engagement detail edits the existing engagement
  instead of creating a new one
- the wizard may jump directly to topic, account, or sending-mode steps, but it
  still validates the full engagement state on `Confirm`
- edit confirmation should update the existing engagement atomically and return
  to engagement detail

## Permission Collapse

### Removed

- `community_engagement_settings.reply_only` stays locked `true` in the MVP.
- `community_engagement_settings.require_approval` stays locked `true` in the
  MVP until backend policy changes explicitly allow otherwise.

### Derived

- `engagement_targets.allow_join` — always `true` once account setup succeeds
- `engagement_targets.allow_detect` — always `true` for both wizard modes
- `engagement_targets.allow_post` — derived from sending mode
- `engagement_targets.status` — implicit:
  `RESOLVED` after target intake, `APPROVED` after successful confirm
- `engagement_settings.allow_join` and `allow_post` — derived from
  sending mode instead of directly edited by the operator

### Hidden

- cadence settings
- quiet hours
- voice/style rules
- prompt profiles
- raw target status transitions
- raw per-action permission toggles

## Callback Namespace

Wizard callbacks live under `eng:wizard:*`:

- `eng:wizard:start` — launch for a new target
- `eng:wizard:step:<n>:<engagement_id>` — navigate to a step
- `eng:wizard:topic:pick:<topic_id>:<engagement_id>` — pick topic
- `eng:wizard:topic:new:<engagement_id>` — create topic sub-flow
- `eng:wizard:account:pick:<account_id>:<engagement_id>` — pick account
- `eng:wizard:account:new:<engagement_id>` — account onboarding sub-flow
- `eng:wizard:mode:<mode>:<engagement_id>` — set sending mode
- `eng:wizard:confirm:<engagement_id>` — confirm final review
- `eng:wizard:cancel:<engagement_id>` — cancel wizard
- `eng:wizard:retry:<engagement_id>` — restart from Step 1

## Code Map

- `bot/engagement_wizard_flow.py` — wizard state resolution, step routing, and
  confirm logic
- `bot/engagement_commands_wizard.py` — command handler wiring
- `bot/formatting_engagement.py` — wizard card formatting
- `bot/ui_engagement.py` — wizard markups and callback builders
- `bot/callback_handlers.py` — `eng:wizard:*` dispatch
- `bot/runtime_config_editing.py` — pending-edit store reused for wizard state
- `backend/api/routes/engagement*.py` — target intake, topic update, settings
  write, detect enqueue

## Validation

- Bot conversation tests for the five steps, including topic/account sub-flows.
- Bot test: abandoned setup restarts from Step 1 instead of resuming.
- Bot test: editing an existing engagement opens prefilled wizard state at the
  tapped step.
- Unit test: `Draft` maps to `suggest`.
- Unit test: `Auto send` maps to `auto_limited`.
- Service test: reusing the same target does not duplicate rows or memberships.
- Service test: confirm never sets `APPROVED` when detect enqueue fails.
- Backend test: `auto_limited` is accepted in the same slice that ships
  `Auto send`.
