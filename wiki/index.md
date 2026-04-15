# Wiki Index

## Spec files
- [Architecture](spec/architecture.md) — Docker Compose layout, data flow, job types, key design rules
- [Database](spec/database.md) — full schema: briefs, communities, members, messages, snapshots, summaries, accounts
- [Audience Brief](spec/audience-brief.md) — keyword extraction and search brief generation
- [Discovery](spec/discovery.md) — TGStat search, candidate community ingestion
- [Expansion](spec/expansion.md) — Telethon seed inspection, graph expansion
- [Collection](spec/collection.md) — public message and member collection from approved communities
- [Analysis](spec/analysis.md) — community summarization and relevance scoring via OpenAI
- [Account Manager](spec/account-manager.md) — Telegram account pool, session management, health tracking
- [API](spec/api.md) — backend REST API, endpoints, auth
- [Bot](spec/bot.md) — Telegram bot operator UI: brief input, candidate review, debug logs
- [Queue](spec/queue.md) — RQ + Redis async workers, scheduling, job states

## Plan files
- [Git CI Convenience](plan/git-ci.md) - repo-local command for staging and committing changes
- [Backend Contracts](plan/backend-contracts.md) — account manager, queue, and API contract plan

## Implementation roots
- `scripts/` - local developer workflow helpers
- `backend/` — FastAPI app, SQLAlchemy models, queue helpers, worker stubs
- `bot/` — Telegram bot package placeholder
- `alembic/` — database migration environment and initial schema migration
- `tests/` — foundation tests for app factory, queue payloads, account manager helpers
