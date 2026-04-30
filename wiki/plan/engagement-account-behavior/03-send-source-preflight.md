# Slice 3: Send Source Preflight

## Goal

Prevent approved replies from sending when the source Telegram message was deleted, inaccessible, or
no longer replyable.

## Scope

- Add an engagement adapter method to verify source-message accessibility and replyability.
- Call the method from `engagement.send` after account lease and before presence/send work.
- Map Telegram source-message failures to skipped audit rows with clear reasons.
- Do not skip merely because newer messages exist in the conversation.

## Code Areas

- `backend/workers/telegram_engagement.py`
- `backend/workers/engagement_send.py`
- `tests/test_telegram_engagement_adapter.py`
- `tests/test_engagement_send_worker.py`

## Acceptance

- Deleted or inaccessible source messages produce a skipped/failed audited send outcome.
- Non-replyable source messages do not call Telethon send.
- Newer conversation messages do not block send.
- Presence read/typing failures remain best effort and do not change audit semantics.

## Dependencies

Can follow Slice 2, but does not require delayed scheduling.
