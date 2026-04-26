# Engagement Add Wizard

Guided five-step setup wizard that walks an operator from a blank community to a running
detection job. Launched from the engagement cockpit's "Add engagement" entry point.

## Purpose

Replace scattered engagement setup (target approval, per-action permissions, account assignment,
mode preset, topic management) with one resumable flow that maps directly to the six worker gates
in `backend/workers/engagement_detect_process.py:19-85`. An operator who completes the wizard
lands in the cockpit with engagement running.

## Goals

- One question at a time. No multi-field forms.
- Each "Continue" button is gated on the real precondition; the wizard cannot reach Launch with a
  broken setup.
- Pick-or-create at every step where reuse is possible (topics, accounts).
- Re-entry resumes from the first incomplete step without duplicating rows, re-triggering joins,
  or restarting topic attachments.
- Hide internal terminology (`status`, `permissions`, `mode`, `target`). Operator vocabulary is:
  community, topic, account, level.

## Non-Goals

- No new conversation framework. Reuse the pending-edit store from the topic create flow.
- No new "draft" model. Partial state lives on real rows in pre-`APPROVED` status.
- No exposure of `engagement_targets.status`, per-action permission flags, MVP-locked settings,
  voice rules, or prompt profiles inside the wizard.
- No change to MVP send-approval semantics. Sends still require human approval.
- No automatic retry policy beyond what existing workers provide.

## Wizard Flow

```text
Community  ->  Topic(s)  ->  Account  ->  Level  ->  Launch
```

Entry point: "Add engagement" button in the engagement cockpit, or `/add_engagement_target`
when called without an existing approved target for that community.

## Step Contracts

### Step 1 — Community

- Prompt: "Which community? Paste @handle or t.me/... link."
- Internal effect: resolve via engagement target intake. If no target row exists, create one at
  `RESOLVED`. If a target already exists at `RESOLVED` or earlier, continue setup with it.
- Pick-or-create:
  - Target at `RESOLVED` or earlier → continue.
  - Target at `APPROVED` → exit the wizard and open the cockpit for that community.
- Success gate: engagement target row exists for this community.
- Failure modes:
  - Resolution fails (private, deleted, not found) → exit with operator-friendly reason. No
    target row is created.
  - Invalid string → re-prompt without state changes.

### Step 2 — Topic(s)

- Prompt: "Pick at least one topic the bot should watch for."
- Pick-or-create:
  - Existing topics in the topic library → multi-select.
  - "Create new" → enter the step flow from `wiki/plan/topic-create-question-flow.md`. On
    finish, return here with the new topic preselected.
- Internal effect: **No per-community topic relation exists in the database.** Topics are global
  (`EngagementTopic` with `active` flag) and the detection worker uses all active topics.
  "Attachment" in the wizard means storing the operator's selected topic IDs in the pending-edit
  `flow_state['topic_ids']` and forcing `active=True` on each selected topic via the update API.
  The launch summary card lists only the operator's selected topics for context.
  No `community_topics` table or migration is needed.
- Success gate: at least one topic ID in `flow_state['topic_ids']`.
- Skip rules:
  - If the topic library is empty, skip the picker and go straight to topic create.
  - If the operator's selection matches what is already attached, advance without redoing attach.
- Failure modes:
  - Topic create aborts → return to Step 2 with no topics attached, allow retry.

### Step 3 — Account

- Prompt: "Which account should engage from?"
- Pick-or-create:
  - Existing ENGAGEMENT-pool accounts → list, "Add new account" as last option.
  - "Add new account" → run phone-verification as a sub-flow. On success, new account joins
    the ENGAGEMENT pool and is preselected when Step 3 resumes.
- Internal effect:
  1. Set `assigned_account_id` on `community_engagement_settings`.
  2. Trigger `community.join` for the community using that account.
  3. Stream join progress in the wizard message ("joining…" → "joined ✓" or failure).
- Success gate: a `CommunityAccountMembership` row exists for the assigned account and
  community.
- Skip rules:
  - Exactly one ENGAGEMENT-pool account → auto-pick, still trigger join.
  - Account has already joined this community → skip join and advance.
  - Pool empty → skip the picker and go straight to the inline account-create sub-flow.
- Failure modes:
  - Account banned, restricted, or unable to join → offer another account or inline account
    create. Never leave operator stuck.
  - FloodWait on join → show retry-after timing; operator retries without restarting the wizard.
  - Account-create aborts → return to the picker with no account assigned, allow retry.

### Step 4 — Level

- Prompt: "How active should this engagement be?"
- Choices (single-select):
  - **Watching** — detect only, never queue replies.
  - **Suggesting** *(default)* — queue reply opportunities for review, do not send.
  - **Sending** — post approved replies after operator review.
- Mode mapping (canonical, must match preset table in
  `wiki/plan/engagement-operator-controls/surface.md`):
  - Watching → `OBSERVE`
  - Suggesting → `SUGGEST`
  - Sending → `REQUIRE_APPROVAL`
- Internal effect: write the chosen mode to `community_engagement_settings.mode`. Derive
  per-action flags as documented in the permission collapse section below.
- Success gate: settings row records the chosen Level.
- Skip rules: none. Operator must pick one Level.

### Step 5 — Launch

- Prompt: summary card — community, attached topics, assigned account, chosen Level — with a
  single "Start engagement" button.
- Internal effect (atomic):
  1. Enqueue first `engagement.detect` job for this community.
  2. Only on enqueue acceptance, flip the engagement target's `status` to `APPROVED`.
  3. Show "Started ✓ — first results will appear in the cockpit shortly."
  4. Redirect operator to the cockpit view for this community.
- Success gate: detect job accepted AND target at `APPROVED`.
- Failure modes:
  - Detect enqueue fails → leave target at pre-launch status, stay in wizard with "Retry"
    button and queue error reason. Operator never lands in a half-broken cockpit.

## Resume Behavior

Wizard entry reads current state of target row, settings row, account membership rows, and
topic-community relations. First incomplete step is determined as:

1. No target row → Step 1.
2. Target exists, no attached active topic → Step 2.
3. No assigned account or no joined membership for that account → Step 3.
4. Settings mode unset → Step 4.
5. All satisfied → Step 5.

If the target is already at `APPROVED`, the wizard exits and opens the cockpit for that
community. A community paused via cockpit settings (`mode=DISABLED`) stays in cockpit world;
the wizard does not reopen for it.

Each step is idempotent. Re-running it must not duplicate rows, re-trigger destructive
operations, or restart already-completed join progress.

## Cancellation

- `/cancel_edit` is active throughout the wizard, matching the topic create flow.
- Cancellation leaves partial state in place (target row at `RESOLVED`, attached topics,
  assigned account if already joined).
- Re-entry resumes from the first incomplete step.
- Cancellation never triggers `APPROVED`. A cancelled wizard cannot start engagement.

## Permission Collapse

The wizard replaces operator-facing toggles with derived values and removes MVP-locked flags.

### Removed (MVP-locked, single-valued)

- `community_engagement_settings.reply_only` — locked `true`. Drop from the API request schema
  and operator-facing settings UI. Keep the column and hardcode writes to `true` until the
  constraint is lifted.
- `community_engagement_settings.require_approval` — locked `true`. Same treatment.

### Derived (no longer operator-facing)

- `engagement_targets.allow_join` — always `true` once Step 3 succeeds. The account membership
  row is the real join state; this flag is redundant. Stop toggling it from the wizard.
- `engagement_targets.allow_detect`, `allow_post` — derived from Level:
  - Watching: `allow_detect=true`, `allow_post=false`
  - Suggesting: `allow_detect=true`, `allow_post=false`
  - Sending: `allow_detect=true`, `allow_post=true`
- `engagement_targets.status` — operator never sees the six-state machine. Wizard transitions
  it implicitly: `RESOLVED` after Step 1, `APPROVED` after Step 5.
- `community_engagement_settings.allow_join`, `allow_post` — same Level-derived mapping.
  Worker double-checks in `engagement_detect_process.py:48-51` and `engagement_send.py:119-125`
  become redundant once `mode` is the single source of truth.

### Hidden (kept in cockpit, not in wizard)

- Cadence (`max_posts_per_day`, `min_minutes_between_posts`) → cockpit settings tab.
- Quiet hours (`quiet_hours_start`, `quiet_hours_end`) → cockpit settings tab.
- Voice and style rules at any scope → cockpit library area.
- Prompt profiles → cockpit library area.
- Per-target raw status transitions and per-action permission toggles → admin surfaces only.

## Callback Namespace

Wizard callbacks live under `eng:wizard:*`:

- `eng:wizard:start` — launch wizard for a new community
- `eng:wizard:step:<n>:<community_id>` — navigate to a step
- `eng:wizard:topic:pick:<topic_id>:<community_id>` — toggle topic selection
- `eng:wizard:topic:new:<community_id>` — enter topic create sub-flow
- `eng:wizard:account:pick:<account_id>:<community_id>` — select account
- `eng:wizard:account:new:<community_id>` — enter account onboarding sub-flow
- `eng:wizard:level:<level>:<community_id>` — set level (watching|suggesting|sending)
- `eng:wizard:launch:<community_id>` — confirm and start engagement
- `eng:wizard:retry:<community_id>` — retry failed launch enqueue

## Code Map

- `bot/engagement_wizard_flow.py` — wizard state resolution, step routing, and launch logic.
- `bot/engagement_commands_wizard.py` — command handler wiring for wizard entry points.
- `bot/formatting_engagement.py` — wizard card formatting.
- `bot/ui_engagement.py` — wizard inline markups and `eng:wizard:*` callback data builders.
- `bot/callback_handlers.py` — `eng:wizard:*` dispatch routing.
- `bot/runtime_config_editing.py` — pending-edit store reused for wizard step state.
- `backend/api/routes/engagement*.py` — target intake, topic attach, settings write, detect
  enqueue endpoints consumed by the wizard.

## Migration Notes

Removing locked flags is staged:

1. Drop `reply_only` and `require_approval` from the API request schema and operator UI. Keep
   the columns; hardcode writes to `true`.
2. After one release with no rollback, drop the columns in an Alembic migration.

Existing communities at `mode = DISABLED` continue to work. The wizard never produces
`DISABLED`; an operator flips off via cockpit settings.

## Validation

- Bot conversation tests: each step including resume from partial state, pick-or-create
  branches, auto-pick when single option, and gate-failure messages.
- Service tests: auto-resolve, auto-approve, and auto-attach flows triggered on operator behalf.
- Unit test: each Level selection maps deterministically to documented engagement mode and
  derived per-action flags on both target and settings rows.
- Unit test: `community_engagement_settings` create and update reject
  `require_approval=False` or `reply_only=False` while the MVP constraint stands.
- Service test: re-entering a partially configured community does not duplicate target rows,
  topic attachments, or account memberships.
- `python scripts/check_fragmentation.py`, `ruff check .`, `pytest -q`.
