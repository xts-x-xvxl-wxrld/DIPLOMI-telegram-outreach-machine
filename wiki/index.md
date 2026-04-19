# Wiki Index

## Spec files

- [Architecture](spec/architecture.md) - Docker Compose layout, seed-first data flow, job types, key design rules
- [Database](spec/database.md) - full schema: seed groups, communities, provenance edges, members, messages, snapshots, summaries, accounts
- [Audience Brief](spec/audience-brief.md) - optional/future keyword extraction and search context
- [Discovery](spec/discovery.md) - seed-first discovery model, candidate normalization, ordering, safety rules
- [Expansion](spec/expansion.md) - Telethon seed-group graph expansion and provenance
- [Collection](spec/collection.md) - public message and member collection from approved communities
- [Analysis](spec/analysis.md) - community summarization and relevance scoring via OpenAI
- [Engagement](spec/engagement.md) - optional operator-approved community joining, topic detection, reply drafting, sending, and audit logs
- [Account Manager](spec/account-manager.md) - Telegram account pool, session management, health tracking
- [API](spec/api.md) - backend REST API, endpoints, auth
- [Bot](spec/bot.md) - Telegram bot operator UI: seed import, candidate review, debug logs
- [Queue](spec/queue.md) - RQ + Redis async workers, scheduling, job states
- [Deployment](spec/deployment.md) - GitHub CI, VPS deploy, secrets, and server-agent branch safety

## Plan files

- [Git CI Convenience](plan/git-ci.md) - repo-local command for staging and committing changes
- [VPS GitHub Pipeline](plan/vps-github-pipeline.md) - safe branch-to-GitHub-to-VPS deployment workflow
- [CI Packaging Install](plan/ci-packaging-install.md) - explicit package discovery for CI and Docker installs
- [Backend Contracts](plan/backend-contracts.md) - account manager, queue, and API contract plan
- [Brief Discovery Slice](plan/brief-discovery-slice.md) - legacy/optional brief-first discovery plan
- [Manual Seed CSV Import](plan/manual-seed-csv-import.md) - bot CSV upload for named manual seed groups
- [Bare Seed Collection](plan/bare-seed-collection.md) - active seed-only flow: resolve imported seeds, collect metadata and members, pause expansion
- [Seed Resolution](plan/seed-resolution.md) - contract and next slice for resolving imported seeds into communities
- [Seed Batch Expansion](plan/seed-batch-expansion.md) - first-class expansion from resolved manual seed groups
- [Seed-First Discovery](plan/seed-first-discovery.md) - active MVP plan replacing briefs with example-community seed groups
- [Telegram Bot UX Control Surface](plan/tg-bot-ux-control-surface.md) - richer Telegram-native operator controls for seed-group review and collection
- [Member Access + Account Onboarding](plan/member-access-onboarding.md) - API/bot member visibility and local Telethon session setup
- [TGStat Removal](plan/tgstat-removal.md) - retire TGStat and replace it with seed, web-search, and graph discovery
- [Docker DNS for Telegram](plan/docker-dns-telegram.md) - local container DNS override for Telegram API access
- [Seed CSV Helper](plan/seed-csv-helper.md) - helper for turning Telegram usernames or links into bot-ready seed CSVs
- [Direct Telegram Entity Intake](plan/direct-telegram-entity-intake.md) - bot text intake for classifying one Telegram handle
- [Bot Operator Access](plan/bot-operator-access.md) - allowlisted Telegram bot operators and `/whoami` onboarding
- [VPS Agent Ops Context](plan/vps-agent-ops.md) - redacted VPS map, helper commands, and staging deploy gates
- [Community Engagement](plan/community-engagement.md) - human-in-the-loop Telethon joining and public reply workflow

## Implementation roots

- `bot/api_client.py` - bot HTTP client for backend API endpoints
- `bot/formatting.py` - concise Telegram message formatting helpers
- `bot/main.py` - Telegram bot command and callback handlers for seed-group operations
- `bot/ui.py` - Telegram keyboard and callback-data helpers for inline operator actions
- `scripts/make_seed_csv.py` - builds bot-ready seed CSV files from public Telegram usernames or links
- `scripts/onboard_telegram_account.py` - local Telethon session creation and `telegram_accounts` registration
- `scripts/vps-deploy.sh` - reset-only staging deploy script for the VPS checkout
- `scripts/vps-deploy-env.sh` - validated environment wrapper around the deploy checkout script
- `scripts/vps-install-agent-ops.sh` - installs the redacted VPS context and helper commands under `/srv/tg-outreach`
- `scripts/vps-logs.sh` - bounded Docker log helper for staging/production services
- `scripts/vps-status.sh` - non-secret VPS status helper for Git, containers, health, and ports
- `scripts/vps-agent-worktree.sh` - helper for branch-scoped VPS coding-agent worktrees
- `ops/vps/AGENT_CONTEXT.md` - redacted VPS architecture map for coding agents
- `.github/workflows/ci.yml` - branch and pull-request validation workflow
- `.github/workflows/deploy-vps.yml` - staging VPS deployment workflow
- `backend/api/routes/seeds.py` - manual seed import and seed-group API endpoints
- `backend/api/routes/engagement.py` - engagement settings and topic-management API endpoints
- `backend/api/routes/telegram_entities.py` - direct Telegram handle intake API endpoints
- `backend/services/community_engagement.py` - engagement settings and topic validation/state service
- `backend/workers/community_join.py` - `community.join` orchestration with membership and audit updates
- `backend/workers/engagement_detect.py` - `engagement.detect` orchestration, sample prefiltering, model calls, and candidate creation
- `backend/workers/engagement_scheduler.py` - low-frequency engagement detection scheduler target selection and enqueueing
- `backend/workers/engagement_send.py` - `engagement.send` orchestration, idempotent action audit, rate-limit checks, and public reply sends
- `backend/workers/telegram_engagement.py` - fakeable Telethon adapter for engagement joins and sends
- `backend/services/seed_import.py` - CSV parsing and seed-group upsert logic
- `backend/services/telegram_entity_intake.py` - direct Telegram handle intake persistence and classification rules
- `backend/services/seed_resolution.py` - manual seed resolver persistence and fakeable adapter contract
- `backend/services/seed_expansion.py` - seed-group expansion persistence and provenance logic
- `backend/workers/brief_process.py` - optional `brief.process` OpenAI extraction and discovery chaining
- `backend/workers/seed_resolve.py` - `seed.resolve` worker orchestration and account release handling
- `backend/workers/seed_expand.py` - `seed.expand` worker orchestration and account release handling
- `backend/workers/telegram_entity_resolve.py` - `telegram_entity.resolve` worker orchestration and account release handling
- `backend/workers/telegram_resolver.py` - Telethon public community entity resolver
- `backend/workers/telegram_entity_resolver.py` - Telethon classifier for one submitted handle
- `backend/workers/telegram_expansion.py` - Telethon seed graph adapter shell
- `alembic/versions/20260419_0006_engagement_schema.py` - engagement schema foundation migration
- `tests/test_engagement_schema.py` - engagement schema enum/default/constraint/index tests
- `tests/test_engagement_detect_worker.py` - engagement detection worker prefiltering, candidate creation, and dedupe tests
- `tests/test_engagement_send_worker.py` - engagement send worker preflight, rate-limit, idempotency, and Telethon error-mapping tests
- `scripts/` - local developer workflow helpers
- `backend/` - FastAPI app, SQLAlchemy models, queue helpers, worker stubs
- `bot/` - Telegram bot package placeholder
- `alembic/` - database migration environment and schema migrations
- `tests/` - foundation tests for app factory, queue payloads, account manager helpers, seeds, and expansion
