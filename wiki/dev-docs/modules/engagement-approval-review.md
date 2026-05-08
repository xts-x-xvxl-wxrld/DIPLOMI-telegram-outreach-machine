# Engagement Approval Review

## Purpose

Document the narrow seam that builds task-first approval queue payloads and turns them into Telegram
review cards.

## Owns

- approval queue payload shaping for the current draft card
- operator-facing engagement/community labels used on approval review screens
- Telegram copy for approval cards, confirm prompts, edit prompts, and placeholder states

## Does Not Own

- candidate selection and approval eligibility rules beyond what the cockpit service exposes
- approval/reject/edit mutations themselves
- issue queue, engagement detail, or sent-feed formatting

## Read First

- `backend/services/task_first_engagement_cockpit.py`
- `backend/api/schemas.py`
- `bot/engagement_approval_flow.py`
- `bot/formatting_engagement_approval.py`

## Entrypoints And Facades

- `get_cockpit_approvals()` in `backend/services/task_first_engagement_cockpit.py`
  - shapes `current` for global and scoped approval queues
- `CockpitApprovalItemOut` in `backend/api/schemas.py`
  - pins the bot-visible response contract for the current draft card
- `show_global_approval_queue()` and `show_draft_card()` in `bot/engagement_approval_flow.py`
  - fetch the queue and send the formatted Telegram messages

## Main Dependencies

- `_engagement_primary_label()` and `_community_label()` in the cockpit service
- `Engagement`, `EngagementCandidate`, and `EngagementDraftUpdateRequest`
- `tests/test_bot_engagement_approval_handlers.py`
- `tests/test_engagement_api.py -k cockpit_approvals`

## Invariants And Boundaries

- `target_label` remains the card heading; it is the composite engagement/community display already
  used elsewhere in the cockpit
- `engagement_label` is the primary engagement label fallback chain:
  `engagement.name` -> topic name -> community title -> engagement UUID
- `community_label` is the community fallback chain:
  `@username` -> community title -> community UUID
- normal approval review surfaces intentionally avoid raw `Draft ID` and `Engagement ID` lines even
  though callback routing still depends on those UUIDs
- placeholder-only queues still use `Updating draft` and do not fabricate a draft card

## Related Tests

- `tests/test_bot_engagement_approval_handlers.py`
- `tests/test_engagement_api.py` filtered with `cockpit_approvals`

## Common Change Patterns

- add or rename review-card fields in the cockpit service first, then mirror them in
  `CockpitApprovalItemOut`, then update `bot/formatting_engagement_approval.py`
- if operator-facing review copy changes, update the bot spec and the approval-handler tests in the
  same patch

## Footguns

- `show_draft_card()` and confirm/edit prompt handlers fall back to a minimal local draft payload
  when the selected draft is no longer current; if you add required display fields, preserve safe
  fallbacks for that path
- approval result messages and callback payloads still carry UUIDs internally; only the review copy
  was made friendlier

## Open Questions

- none from this inspection
