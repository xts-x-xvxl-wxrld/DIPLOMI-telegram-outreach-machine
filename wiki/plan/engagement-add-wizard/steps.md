# Engagement Add Wizard Steps

Detailed step contracts for the engagement add wizard described in
`wiki/plan/engagement-add-wizard/overview.md`. Each step lists its operator-facing prompt, the
internal effect, the success gate, skip and auto-pick rules, and failure modes.

## Step 1: Target

- Prompt: "Which community? Paste @handle or t.me/... link."
- Internal effect: resolve via the existing engagement target intake. If no engagement target row
  exists for the resolved community, create one in `RESOLVED` status.
- Pick-or-create:
  - Existing target at `RESOLVED` or earlier → continue setup.
  - Existing target at `APPROVED` → exit the wizard and open the cockpit for that community.
- Success gate: an engagement target row exists for this community.
- Failure modes:
  - Resolution fails (private, deleted, not found) → exit with an operator-friendly reason. No
    target row is created.
  - Operator pastes an invalid string → re-prompt without state changes.

## Step 2: Topic

- Prompt: "Choose a topic or create a new one."
- Pick-or-create:
  - Existing topics in the topic library → single-choice picker.
  - "Create new" → enter the flow defined in `wiki/plan/topic-create-question-flow.md`. On finish,
    return here with the new topic selected.
- Internal effect: write exactly one chosen topic to the draft engagement. Force `active=true` on
  any topic the operator selects or creates.
- Success gate: one active topic is attached to this engagement.
- Skip rules:
  - If the topic library is empty, skip the picker and go straight to topic create.
  - If the operator's selection matches the current engagement topic (returning to the wizard),
    advance without redoing the write.
- Failure modes:
  - Topic create flow aborts → return to Step 2 with no topic selected, allow retry.

## Step 3: Account

- Prompt: "Which account should engage from?"
- Pick-or-create:
  - Existing accounts in the ENGAGEMENT pool → list, with "Add new account" as the last option.
  - "Add new account" → run phone-verification as a sub-flow inside the wizard. On success, the
    new account joins the ENGAGEMENT pool and is preselected when control returns to Step 3.
- Internal effect:
  1. Set `assigned_account_id` on engagement-scoped settings.
  2. Trigger `community.join` for the community using that account.
  3. Stream join progress in the wizard message ("joining…" → "joined ✓" or failure).
- Success gate: a `CommunityAccountMembership` row exists for the assigned account and community.
- Skip rules:
  - Exactly one ENGAGEMENT-pool account exists → auto-pick, still trigger join.
  - Account has already joined this community → skip the join step and advance.
  - Engagement pool empty → skip the picker and go straight to the inline account-create sub-flow.
- Failure modes:
  - Account banned, restricted, or unable to join → offer another account or run the inline
    account-create sub-flow.
  - FloodWait on join → show retry-after timing and let the operator retry without restarting the
    wizard.
  - Account-create sub-flow aborts → return to the picker with no account assigned, allow retry.

## Step 4: Sending Mode

- Prompt: "How should sending work?"
- Choices:
  - `Draft` (default) — create draft replies for operator approval.
  - `Auto send` — allow capped automatic sends after setup.
- Internal effect: write the corresponding engagement mode to
  `engagement_settings.mode`. Drop redundant per-action and MVP-locked flags as
  described in `wiki/plan/engagement-add-wizard/collapse.md`.
- Mode mapping (canonical):
  - `Draft` → `SUGGEST`
  - `Auto send` → `AUTO_LIMITED`
- Derived flags:
  - `Draft` → `allow_detect=true`, `allow_post=false`
  - `Auto send` → `allow_detect=true`, `allow_post=true`
- Success gate: settings row records the chosen sending mode.
- Skip rules: none.
- Rule: no detect-only option exists in the wizard.
- Implementation requirement: MVP validation currently rejects `AUTO_LIMITED`;
  that guard must be removed in the same slice that ships `Auto send`.

## Step 5: Final Review

- Prompt: a read-only summary card showing target, chosen topic, account, and
  chosen sending mode.
- Actions:
  - `Confirm`
  - `Cancel`
  - `Retry`
- Internal effect (atomic — all-or-nothing):
  1. Validate target, topic, joined account, and sending mode on the draft engagement.
  2. Enqueue the first `engagement.detect` job for this engagement's community.
  3. Only on enqueue acceptance, flip the engagement target's `status` to `APPROVED` and
     activate the engagement.
  3. Show "Started ✓ — first results will appear in the cockpit shortly."
  4. Redirect the operator to the engagement detail view for this engagement.
- Success gate: detect job accepted by the queue, target at `APPROVED`, and engagement active.
- Failure modes:
  - Detect enqueue fails (queue down) → leave the target at its pre-review
    status, stay on final review, and show the queue error.
- Behavior:
  - `Retry` restarts the wizard from Step 1.
  - `Cancel` requires confirmation before discard.

## Start-Again Behavior

- `Add engagement` always starts at Step 1.
- The wizard does not reopen abandoned setup where it left off.
- Temporary wizard state is cleared on fresh entry.
- Durable rows created in a previous attempt may still be reused safely once the
  operator chooses the same target again.
- Editing an existing engagement is separate:
  - it reopens the full wizard with prefilled values
  - it jumps to the tapped step
  - it still allows backward navigation

## Cancellation

- `/cancel_edit` is active throughout the wizard, matching the topic create flow precedent.
- Cancellation may leave durable rows in place, but abandoned setup is not
  treated as resumable flow state.
- Cancellation never triggers `APPROVED`. A cancelled wizard cannot start engagement.
