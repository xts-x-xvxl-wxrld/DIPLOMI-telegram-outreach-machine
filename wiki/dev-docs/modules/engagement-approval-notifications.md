# Engagement Approval Notifications

## Purpose

Document how the active bot proactively sends Telegram alerts for unseen approval drafts.

## Owns

- bot startup/shutdown wiring for the ordinary approval-draft notifier
- per-operator in-memory draft-notification dedupe
- paged approvals-queue scans used to find unseen draft IDs
- Telegram message delivery for proactive ordinary-draft review cards

## Does Not Own

- draft queue ordering or payload shaping beyond the existing approvals API contract
- approval/reject/edit mutations themselves
- delayed revised-draft follow-up logic after `Request edit`

## Read First

- `bot/engagement_approval_notifications.py`
- `bot/app.py`
- `bot/engagement_approval_flow.py`
- `backend/services/task_first_engagement_cockpit.py`

## Entrypoints And Facades

- `start_approval_draft_notifier()` in `bot/engagement_approval_notifications.py`
  - starts the background polling task when explicit operator IDs are configured
- `send_new_approval_draft_notifications()` in `bot/engagement_approval_notifications.py`
  - pages the approvals queue, finds unseen draft IDs, and sends proactive draft cards
- `mark_approval_draft_notified()` in `bot/engagement_approval_notifications.py`
  - shared in-memory dedupe seam used by both ordinary-draft alerts and revised-draft follow-ups
- `post_init()` / `post_shutdown()` in `bot/app.py`
  - start and stop the ordinary approval notifier with the Telegram application lifecycle

## Invariants And Boundaries

- the notifier only targets explicit operator IDs from bot settings; it does not infer recipients
  from recent chat activity
- dedupe is per operator and per draft ID for the current bot-process lifetime only
- ordinary-draft notifications reuse the same task-first draft card format and approval actions as
  the interactive approvals queue
- the notifier scans the active approvals queue through the bot API client; it does not read the
  database directly or call worker code
- revised-draft watchers and ordinary-draft alerts share the same notified-draft store so one draft
  should not emit two proactive messages for the same operator in one bot process

## Footguns

- notification dedupe is in-memory only; a bot restart can resend still-pending drafts because no
  durable acknowledgement is written yet
- if the queue grows quickly, the notifier may send more than one Telegram message in one scan
  because it pages every visible draft ID
- operators who never started the bot or blocked it will make `send_message` fail; the notifier logs
  and skips without marking the draft as delivered

## Related Tests

- `tests/test_bot_engagement_approval_notifications.py`
- `tests/test_bot_startup_commands.py`
- `tests/test_bot_engagement_approval_edit_flow.py`
