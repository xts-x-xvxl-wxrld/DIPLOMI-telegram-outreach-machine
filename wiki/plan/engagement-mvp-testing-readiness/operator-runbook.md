# Engagement MVP Operator Runbook Slice

## Slice 5: Operator Staged-Test Controls

Status: planned.

Tasks:

- Ensure the API can manually queue engagement collection for an approved target.
- Ensure the bot exposes or links the staged sequence:
  - target status
  - join job
  - manual collection job
  - manual detection job
  - reply opportunity review/edit
  - approve/send
  - action audit view
- Add concise bot copy that says `reply opportunity` even when calling legacy candidate endpoints.
- Expose collection run status enough for an operator to see whether fresh messages were collected.

Acceptance:

- A tester can run the whole MVP sequence from the bot without direct database edits.
- Manual collection refuses unapproved targets.
- Manual send still requires an approved reply opportunity and joined engagement membership.

## Slice 6: Staged Telegram Runbook

Status: planned.

Tasks:

- Add a short runbook under `wiki/plan/` or `ops/` for:
  - fake-adapter/local unit test pass
  - controlled Telegram group dry run
  - one real approved community observe-only run
  - one approved reply-only send
- Include preflight checks:
  - `telegram_accounts.account_pool = 'engagement'` for send/join account
  - engagement target is approved with only the needed permissions
  - settings require approval and reply-only mode
  - quiet hours and rate limits are conservative
  - OpenAI key/model settings are present for detection
  - raw message storage remains off unless explicitly enabled for diagnosis
- Include abort switches:
  - set engagement settings to `disabled`
  - pause collection scheduler
  - reject or expire pending reply opportunities

Acceptance:

- The runbook can be followed by an operator without reading source code.
- The runbook includes expected database/API/bot evidence for collection, detection, review, send,
  and audit.
- The runbook explicitly forbids DMs, auto-send, and bulk posting during MVP testing.

## MVP Test Definition Of Done

The MVP engagement path is ready for staged Telegram testing when all of these are true:

- One approved target can be joined by a dedicated engagement account.
- A collection run can fetch fresh public messages and persist an exact engagement batch.
- Detection can create a bounded, fresh reply opportunity from that exact batch.
- The operator can review, edit, approve, and send one public reply.
- The action audit row stores the exact outbound text, target message ID, send status, and error
  details when applicable.
- No collection path calls OpenAI or writes engagement decision rows.
- No send path can bypass approval, target permission, joined membership, reply-only mode, quiet
  hours, or rate limits.

## Out Of Scope

- Automatic sending.
- Direct messages.
- Bulk joining or bulk posting.
- Dedicated engagement batch table.
- Person-level scores, user ranking, or private identity enrichment.
- Rewriting legacy `engagement_candidates` storage names.
