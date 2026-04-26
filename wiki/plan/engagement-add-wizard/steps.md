# Engagement Add Wizard Steps

Detailed step contracts for the engagement add wizard described in
`wiki/plan/engagement-add-wizard/overview.md`. Each step lists its operator-facing prompt, the
internal effect, the success gate, skip and auto-pick rules, and failure modes.

## Step 1: Community

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

## Step 2: Topic(s)

- Prompt: "Pick at least one topic the bot should watch for."
- Pick-or-create:
  - Existing topics in the topic library → multi-select.
  - "Create new" → enter the flow defined in `wiki/plan/topic-create-question-flow.md`. On finish,
    return here with the new topic preselected.
- Internal effect: attach selected topics to this community via the existing topic-community
  relation. Force `active=true` on any topic the operator selects or creates.
- Success gate: at least one active topic is attached to this community.
- Skip rules:
  - If the topic library is empty, skip the picker and go straight to topic create.
  - If the operator's selection matches what is already attached (returning to the wizard),
    advance without redoing the attach.
- Failure modes:
  - Topic create flow aborts → return to Step 2 with no topics attached, allow retry.

## Step 3: Account

- Prompt: "Which account should engage from?"
- Pick-or-create:
  - Existing accounts in the ENGAGEMENT pool → list, with "Add new account" as the last option.
  - "Add new account" → run phone-verification as a sub-flow inside the wizard. On success, the
    new account joins the ENGAGEMENT pool and is preselected when control returns to Step 3.
- Internal effect:
  1. Set `assigned_account_id` on `community_engagement_settings`.
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

## Step 4: Level

- Prompt: "How active should this engagement be?"
- Choices (single-select radio):
  - **Watching** — detect only, never queue replies.
  - **Suggesting** (default) — queue replies for operator review, do not send automatically.
  - **Sending** — post approved replies after operator review.
- Internal effect: write the corresponding engagement mode to
  `community_engagement_settings.mode`. Drop redundant per-action and MVP-locked flags as described
  in `wiki/plan/engagement-add-wizard/collapse.md`.
- Mode mapping (canonical):
  - Watching → `OBSERVE`
  - Suggesting → `SUGGEST`
  - Sending → `REQUIRE_APPROVAL`
- Success gate: settings row records the chosen Level via the mapped mode.
- Skip rules: none. The operator must pick one Level.

## Step 5: Launch

- Prompt: a summary card showing community, attached topics, assigned account, and chosen Level.
  One primary button labeled "Start engagement."
- Internal effect (atomic — all-or-nothing):
  1. Enqueue the first `engagement.detect` job for this community.
  2. Only on enqueue acceptance, flip the engagement target's `status` to `APPROVED`.
  3. Show "Started ✓ — first results will appear in the cockpit shortly."
  4. Redirect the operator to the cockpit view for this community.
- Success gate: detect job accepted by the queue AND target at `APPROVED`.
- Failure modes:
  - Detect enqueue fails (queue down) → leave the target at its pre-launch status, stay in the
    wizard with a "Retry" button and the queue error reason. Operator never lands in a half-broken
    cockpit.

## Resume Behavior

- Wizard entry reads current state of the target row, settings row, account membership rows, and
  topic-community relations for this community.
- If the target is already at `APPROVED`, the wizard exits and opens the cockpit for that
  community. A community paused via cockpit settings (mode=DISABLED) stays in cockpit world; the
  wizard does not reopen for it.
- Otherwise, the first incomplete step is determined as:
  1. No target row → Step 1.
  2. Target exists but no attached active topic → Step 2.
  3. No assigned account or no joined membership for that account → Step 3.
  4. Settings mode unset → Step 4.
  5. All of the above satisfied → Step 5.
- Each step is idempotent. Re-running it must not duplicate rows, re-trigger destructive
  operations, or restart already-completed join progress.

## Cancellation

- `/cancel_edit` is active throughout the wizard, matching the topic create flow precedent.
- Cancellation leaves any partial state in place (target row at `RESOLVED`, attached topics,
  assigned account if already joined). Re-entry resumes from the first incomplete step.
- Cancellation never triggers `APPROVED`. A cancelled wizard cannot start engagement.
