# Engagement Cockpit Verification Plan

## Goal

Audit the task-first Telegram engagement cockpit against the active UX spec,
verify each operator path in code, and harden the contract with regression
tests before fixing confirmed defects.

## Source Of Truth

Active UX source of truth:

- `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`

Authority notes:

- `wiki/spec/bot-cockpit-experience/attention-and-navigation.md` explicitly says
  `engagement-task-first-cockpit.md` is the only active source of truth for
  home behavior, top-level issue surfacing, and footer navigation.
- `wiki/spec/bot/engagement-add-wizard.md` is an implementation-contract shard
  under the task-first cockpit UX. It should be used for wizard details only,
  and the task-first cockpit spec wins on any conflict.
- `wiki/spec/bot-engagement-controls/navigation.md` is supporting context for
  operator modes, readiness language, and broader engagement navigation, but it
  must not override the task-first cockpit's home, issue-surface, or footer
  rules.
- `wiki/spec/bot-cockpit-experience.md` is companion context only and is not
  allowed to define competing home-screen, navigation, or wizard-topology
  rules.

## Why This Plan Exists

The engagement cockpit already has broad implementation and test coverage, but
navigation and flow correctness should be verified against the current UX
contract instead of inferred from older behavior or partial tests.

This plan creates one explicit workflow:

1. define intended operator behavior from the active source-of-truth spec
2. map each surface to bot handlers, API endpoints, and test files
3. identify mismatches between spec, code, and tests
4. add or tighten tests for the true contract
5. fix only confirmed failures or contract drift

## Scope

In scope:

- `Engagements` home state and button ordering
- approval queue and draft review actions
- issue queue and issue-fix subflows
- `My engagements`
- engagement detail and resume behavior
- sent-message feed
- add/edit wizard flows
- non-wizard vs wizard navigation rules
- bot/API contract alignment for task-first callbacks

Out of scope:

- legacy pre-task-first engagement home behavior
- discovery cockpit redesign work
- non-bot frontend work
- new engagement product features not already specified

## Audit Inventory

The verification pass should treat these as the operator-facing feature set:

1. `Engagements` home
2. `Approve draft`
3. `Top issues`
4. rate-limit detail
5. quiet-hours edit
6. `My engagements`
7. engagement detail
8. pending-task resume
9. `Sent messages`
10. `Add engagement` wizard
11. engagement edit via wizard
12. navigation outside the wizard
13. navigation inside the wizard

## Verification Workflow

### Phase 1: Spec Baseline

- Extract the intended UX contract for each inventory item from the active spec.
- Record the exact callback family, expected destination, and return behavior.
- Note whether the behavior depends on backend `next_callback`,
  `resume_callback`, or semantic mutation results.

Deliverable:

- a compact matrix of `surface -> callback -> expected behavior`

### Phase 2: Code Mapping

- Map each surface to its bot handler, formatting helper, markup builder, and
  API client method.
- Confirm whether the code path uses task-first callbacks or legacy routes.
- Flag any place where handlers infer workflow state instead of following the
  backend semantic contract.

Primary files expected:

- `bot/callback_handlers.py`
- `bot/engagement_approval_flow.py`
- `bot/engagement_issue_flow.py`
- `bot/engagement_detail_flow.py`
- `bot/engagement_wizard_flow.py`
- `bot/ui_engagement_home.py`
- `bot/ui_engagement_detail.py`
- `bot/ui_engagement_wizard.py`
- `bot/api_client.py`

Deliverable:

- a mapping of `surface -> code entrypoints -> risk notes`

### Phase 3: Test Coverage Review

- Map each surface to existing bot/UI/API tests.
- Separate strong contract tests from weak tests that only assert text, shape,
  or placeholder behavior.
- Identify where current tests accidentally permit broken navigation or wrong
  routing.

Primary files expected:

- `tests/test_bot_engagement_home_handlers.py`
- `tests/test_bot_engagement_approval_handlers.py`
- `tests/test_bot_engagement_issue_handlers.py`
- `tests/test_bot_engagement_detail_handlers.py`
- `tests/test_bot_engagement_wizard.py`
- `tests/test_engagement_api.py`

Deliverable:

- a matrix of `surface -> existing tests -> missing assertions`

### Phase 4: Regression Test Hardening

Write or tighten tests before behavior changes for:

1. issue `next_step` actions dispatching the returned callback
2. reopening the requested issue card by `issue_id`
3. quiet-hours edits using the issue's actual engagement
4. scoped issue queue pagination preserving the target item
5. reopening the requested draft by `draft_id`
6. non-wizard engagement footer navigation returning to `eng:home`
7. engagement detail resume following backend `resume_callback`

Rules:

- Prefer handler-level tests for callback routing behavior.
- Add API tests only when the backend semantic contract itself is unclear or
  unverified.
- Replace permissive tests when they currently bless broken behavior.

### Phase 5: Troubleshooting And Fixes

- Run the focused engagement test set.
- Fix only failures or spec mismatches proven by the audit.
- Re-run focused tests after each cluster of changes.
- Run local parity once the cockpit slice is stable.

## Exit Criteria

This verification slice is done when:

- each in-scope engagement surface is mapped to spec, code, and tests
- critical navigation paths have regression tests for the real contract
- known mismatches are either fixed or recorded as explicit follow-up work
- the engagement cockpit no longer relies on placeholder assertions for core
  navigation behavior

## Suggested Execution Order

1. build the spec-to-code matrix
2. review existing tests against that matrix
3. harden tests for high-risk navigation paths
4. fix confirmed regressions
5. run focused engagement tests
6. run local parity before any commit
