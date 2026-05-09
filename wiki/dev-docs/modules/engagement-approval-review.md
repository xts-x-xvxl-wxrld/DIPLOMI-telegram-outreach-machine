# Engagement Approval Review

## Purpose

Document the narrow seam that builds task-first approval queue payloads and turns them into Telegram
review cards.

## Owns

- approval queue payload shaping for the current draft card
- operator-facing engagement/community labels used on approval review screens
- source-message excerpt handoff from `EngagementCandidate` into review-card payloads
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
- `bot/discovery_handlers.py`
- `bot/engagement_commands_daily.py`

## Entrypoints And Facades

- `get_cockpit_approvals()` in `backend/services/task_first_engagement_cockpit.py`
  - shapes `current` for global and scoped approval queues
- `CockpitApprovalItemOut` in `backend/api/schemas.py`
  - pins the bot-visible response contract for the current draft card
- `show_global_approval_queue()` and `show_draft_card()` in `bot/engagement_approval_flow.py`
  - fetch the queue and send the formatted Telegram messages
- `handle_edit_request_text()` in `bot/engagement_approval_flow.py`
  - submits approval edit requests, clears pending state, briefly polls the scoped approvals queue,
    reopens the replacement draft when the backend already surfaced `Updated draft`, and otherwise
    starts a bounded bot-side watcher that can send a delayed follow-up card when the rewrite lands
- `mark_approval_draft_notified()` in `bot/engagement_approval_notifications.py`
  - shared per-operator dedupe store used when approval drafts are proactively messaged or already
    surfaced interactively in the queue/edit flows
- `post_engagement_cockpit_draft_edit()` in `backend/api/routes/engagement_cockpit.py`
  - persists the draft-update row and enqueues the targeted `engagement.detect.rewrite` worker job
- `process_engagement_detect()` in `backend/workers/engagement_detect_process.py`
  - special-cases `draft_update_request_id` payloads so rewrite jobs reuse the original source draft
    instead of waiting for fresh collection samples
- `telegram_entity_text()` in `bot/discovery_handlers.py`
  - routes free-text follow-up messages into pending approval edit submission before normal
    Telegram-handle intake runs
- `cancel_edit_command()` in `bot/engagement_commands_daily.py`
  - cancels either config-edit state or pending approval-edit state for the same operator
- `resume_edit_command()` in `bot/engagement_commands_daily.py`
  - manually restores the approval-edit prompt from the current or explicit draft ID when pending
    in-memory state was lost

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
- `source_excerpt` comes from `EngagementCandidate.source_excerpt`; it is already sanitized during
  candidate creation, so approval formatting should treat it as display-ready optional text
- normal approval review surfaces intentionally avoid raw `Draft ID` and `Engagement ID` lines even
  though callback routing still depends on those UUIDs
- placeholder-only queues still use `Updating draft` and do not fabricate a draft card
- revised-draft follow-up is bot-only: after queueing an edit request, the bot polls the scoped
  approvals queue for the same engagement and only short-circuits to a draft card when the backend
  marks the current item with `badge = "Updated draft"`
- delayed revised-draft notification is also bot-only: if the short poll misses, the bot keeps a
  per-operator in-memory watcher for a bounded window and sends a new Telegram message once the same
  scoped queue surfaces `badge = "Updated draft"`
- interactive draft views mark the same draft ID as already surfaced for that operator so the
  ordinary startup notifier does not immediately resend a draft card the operator already opened
- draft-update rows are only supposed to hide the source draft while they are `pending` or
  `completed`; failed rewrites must stop hiding the source draft so operators can act again
- rewrite jobs intentionally bypass recent-sample loading and rebuild from the original
  `EngagementCandidate` source message plus the operator's `edit_request`
- rewrite prompt assembly must treat the existing topic/style prompt as the base contract and layer
  the operator edit request on top of the previous draft; edit requests should not implicitly wipe
  out the prior draft's core recommendation or CTA unless the operator asked for that change
- rewrite duplicate suppression must ignore the entire completed/pending revision chain for the same
  engagement, not just the current source draft, otherwise a second edit loop can complete by
  pointing back to an already-hidden historical candidate and make the approvals queue appear empty

## Related Tests

- `tests/test_bot_engagement_approval_handlers.py`
- `tests/test_bot_engagement_approval_ingress.py`
- `tests/test_engagement_api.py` filtered with `cockpit_approvals`

## Common Change Patterns

- add or rename review-card fields in the cockpit service first, then mirror them in
  `CockpitApprovalItemOut`, then update `bot/formatting_engagement_approval.py`
- if operator-facing review copy changes, update the bot spec and the approval-handler tests in the
  same patch
- keep new review-card fields optional unless the stale-draft fallback path in
  `show_draft_card()` is updated to synthesize them safely
- if you change the approval-update badge or queue ordering in the cockpit service, update
  `handle_edit_request_text()` because the revised-draft follow-up depends on the current scoped
  item exposing `badge = "Updated draft"`
- if you change the delayed-notification polling window or task ownership, update the watcher keys
  and approval-edit tests together; only the newest watcher per operator should remain active
- if you change rewrite-job enqueueing or payload fields, keep the API route and
  `backend/workers/engagement_detect_process.py` in sync; the bot does not trigger a second polling
  path beyond the normal approvals refresh

## Footguns

- `show_draft_card()` and confirm/edit prompt handlers fall back to a minimal local draft payload
  when the selected draft is no longer current; if you add required display fields, preserve safe
  fallbacks for that path
- approval result messages and callback payloads still carry UUIDs internally; only the review copy
  was made friendlier
- approval edit capture is split across modules: the callback starts in
  `bot/engagement_approval_flow.py`, but the operator's next plain-text message is consumed in
  `bot/discovery_handlers.py`; if that routing check is removed or reordered, edit requests appear
  to do nothing in Telegram
- the revised-draft follow-up is intentionally short-lived; if the replacement draft takes longer
  than the poll window, operators will still land back in the normal queue/placeholder flow instead
  of waiting indefinitely in Telegram
- the delayed notification watcher is also intentionally in-memory only; a bot restart clears it, so
  this path improves responsiveness but is not a durable delivery guarantee
- a stuck `pending` request usually means the rewrite worker never ran or never completed the row;
  verify the `engagement.detect.rewrite` job and the `EngagementDraftUpdateRequest.status` before
  debugging the bot layer
- manual recovery depends on the approvals queue still exposing either the requested `draft_id` or a
  current top draft; `/resume_edit` cannot restore edits for drafts that have already left the queue

## Open Questions

- none from this inspection
