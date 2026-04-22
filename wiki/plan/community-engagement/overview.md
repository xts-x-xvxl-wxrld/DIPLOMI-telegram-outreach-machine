# Community Engagement Overview

Goal, context, design decisions, open questions, and rollback plan.

## Goal

Add an optional engagement layer that lets managed Telethon accounts join approved communities,
notice active discussion around configured topics, draft useful public replies, and send only after
operator approval.

The first implementation should be conservative and auditable:

```text
settings + topics
  -> join approved community
  -> detect topic moment
  -> draft candidate
  -> operator approves
  -> send public reply
  -> audit action
```
## Current Context

Existing boundaries:

- Discovery finds communities and does not collect raw message history.
- Collection fetches and persists community data only; it has no outreach behavior.
- Analysis produces community-level summaries only.
- Account manager leases one account per worker job and tracks flood waits.
- Raw messages are opt-in through `communities.store_messages`.

Engagement must not weaken those boundaries. It should be a new module with its own jobs, tables,
API routes, bot controls, and audit logs.
## Design Decisions

- Engagement is opt-in per community.
- MVP requires human approval before every send.
- MVP sends public replies only, not direct messages.
- MVP should not send top-level posts unless a later plan explicitly adds that mode.
- Detection may use OpenAI, but only in the engagement worker.
- Collection remains read-only.
- No person-level scoring, ranking, or persuasion targeting.
- Telethon accounts used for engagement must use the account manager and respect FloodWait.
- Every outbound action must be logged, including failed and skipped attempts.
## Open Questions

- Should engagement settings be available only for `status = monitoring` communities, or also for
  approved candidates before recurring collection is enabled?
- Should each community have exactly one assigned Telegram account, or should assignment be chosen
  at send time from eligible joined accounts?
- Should edited suggested replies be stored as a separate revision table or only as final outbound
  text on `engagement_actions`?
- Should `auto_limited` ever be enabled, or remain out of scope permanently?
## Rollback Plan

If engagement creates operational risk:

- Set all `community_engagement_settings.mode = 'disabled'`.
- Disable scheduler enqueueing for `engagement.detect`.
- Keep audit tables for investigation.
- Leave discovery, collection, expansion, and analysis unaffected.
