# Engagement Spec

Top-level routing contract for optional, operator-approved public Telegram engagement. Detailed
workflow, API, bot, prompt, and rollout contracts live in focused shards under `wiki/spec/engagement/`.

## Responsibility

Engagement turns approved community monitoring into human-reviewed public reply opportunities. It
covers target permission gates, topic matching, candidate drafting, review, send orchestration, and
audit trails.

## Non-Goals

- No automated joining or posting without explicit operator permission.
- No direct messages, invite scraping, or private-surface outreach.
- No person-level scoring or profiling.
- No business logic in the collection worker.

## Invariants

- Engagement targets must be explicitly approved before collection, joining, detection, or posting.
- Drafting may suggest replies, but public sends require an approved reply opportunity and outbound
action audit row.
- Collection stores only bounded artifacts needed for community-level matching and drafting.
- OpenAI calls remain in `engagement.detect`; sending and scheduling do not call OpenAI.
- Dedicated engagement account-pool routing is enforced before joins or sends.

## Interface Summary

- `community.join` joins an approved engagement target with an engagement-purpose account.
- `engagement.detect` samples recent approved-target activity, matches topics, drafts candidates,
and notifies operators.
- `engagement.send` revalidates approval, rate limits, and membership state before replying.
- API routes under `backend/api/routes/engagement*.py` expose settings, topics, targets, prompts,
style rules, candidates, actions, and rollout summaries.
- Bot handlers expose daily review and admin control surfaces through the `eng:` callback namespace.

## Code Map

- `backend/api/routes/engagement.py` - compatibility router for engagement route shards.
- `backend/api/routes/engagement_*.py` - target, settings/topic, prompt/style, and candidate/action routes.
- `backend/services/community_engagement.py` - compatibility exports for engagement services.
- `backend/services/community_engagement_*.py` - engagement settings, targets, topics, prompts, style rules, candidates, actions, and shared views.
- `backend/workers/community_join.py` - approved target join orchestration.
- `backend/workers/engagement_detect.py` - compatibility exports for engagement detection worker shards.
- `backend/workers/engagement_detect_*.py` - detection process, samples, selection, prompts, OpenAI, and shared types.
- `backend/workers/engagement_send.py` - reply send preflight, idempotency, and audit writes.
- `backend/workers/engagement_scheduler.py` - low-frequency detection target selection.
- `backend/workers/telegram_engagement.py` - Telethon adapter for joins and replies.
- `bot/formatting_engagement.py` - engagement bot message formatting.
- `bot/ui_engagement.py` - engagement inline controls and callback data builders.

## Shards

- [Lifecycle](engagement/lifecycle.md) - terminology, durable statuses, invariants, ethics, safety.
- [Settings and Membership](engagement/settings-membership.md) - community settings and account memberships.
- [Topics and Drafting](engagement/topics-drafting.md) - topic contracts, trigger selection, prompt rules.
- [Opportunities and Actions](engagement/opportunities-actions.md) - reply opportunities and outbound actions.
- [Jobs and Scheduling](engagement/jobs-scheduling.md) - worker jobs, notification, monitoring cadence.
- [API and Bot Surface](engagement/api-bot.md) - API DTOs and Telegram bot workflows.
- [Observability and Tests](engagement/observability-tests.md) - logs, metrics, and test requirements.

## Open Questions

- Which oversized engagement test surfaces should be split first now that route and service shards are stable?
- Should route/service facades keep monkeypatch compatibility long-term or should tests move directly to shard imports?
