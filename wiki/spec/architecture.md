# Architecture Spec

## Overview

Single-operator Telegram community discovery and monitoring app.
Deployed on a VPS (2-4GB RAM) using Docker Compose.
Fully async job pipeline. Telegram bot as prototype operator UI.

The active MVP is seed-first. The operator supplies example Telegram communities in named
`seed_groups`, the app resolves those examples into real Telegram channel/group records, then
expands outward through explainable Telegram graph evidence. Audience briefs are no longer the
primary discovery input; they remain a future optional context layer for search hints, filtering,
and analysis.

---

## Docker Compose Services

| Service | Image | Role |
|---------|-------|------|
| `api` | FastAPI | REST API: receives bot commands, enqueues jobs, serves results |
| `worker` | Python + RQ | Job runner: seed resolution, expansion, community snapshots, engagement collection, analysis |
| `scheduler` | Python | Lightweight recurring scheduler for optional engagement detection ticks |
| `bot` | Python + python-telegram-bot | Operator UI: seed import, candidate review, debug logs |
| `redis` | redis:alpine | Job queue + RQ result backend |
| `postgres` | postgres:16 | Primary datastore |

All services share one Docker network. Only `api` and `bot` communicate over HTTP. Workers talk
directly to Postgres and Redis.

Services that call Telegram from local Docker (`bot` and `worker`) set explicit public DNS
resolvers so host-level DNS interception does not redirect `api.telegram.org` or Telethon endpoints
to non-Telegram infrastructure.

---

## Repository Layout

Implementation should use this layout unless a later spec explicitly changes it:

```text
backend/
  api/            # FastAPI routes, dependencies, response schemas
  core/           # settings, logging, shared app utilities
  db/             # SQLAlchemy models, sessions, repositories
  queue/          # RQ connection, enqueue helpers, job metadata helpers
  workers/        # seed resolution, expansion, snapshots, engagement collection, analysis, account manager
bot/              # Telegram bot operator UI
alembic/          # database migrations
scripts/          # local developer workflow helpers
docker-compose.yml
.env.example
```

Shared contracts should live in `backend/` and be imported by both API and worker code. The bot
should depend on HTTP responses, not internal Python modules.

---

## Runtime Configuration

Use these environment variable names:

| Variable | Used by | Purpose |
|---|---|---|
| `DATABASE_URL` | api, worker | PostgreSQL connection string |
| `REDIS_URL` | api, worker, scheduler | Redis/RQ connection string |
| `BOT_API_TOKEN` | api, bot | Internal bearer token for bot-to-API calls |
| `OPENAI_API_KEY` | worker | OpenAI API access for optional brief processing and analysis jobs |
| `TELEGRAM_API_ID` | worker | Telegram API ID for Telethon |
| `TELEGRAM_API_HASH` | worker | Telegram API hash for Telethon |
| `SESSIONS_DIR` | worker | Mounted Telethon session directory |
| `COMMUNITY_SNAPSHOT_INTERVAL_MINUTES` | worker | Scheduler interval for discovery community snapshots; default 60 |
| `ENGAGEMENT_DETECTION_WINDOW_MINUTES` | scheduler | Recent collection window required before detection; default 60 |
| `ENGAGEMENT_SCHEDULER_INTERVAL_SECONDS` | scheduler | Engagement scheduler sleep interval; default 3600 |

Secrets must not be committed. `.env.example` may list variable names with empty values.

## OpenAI Usage Boundary

OpenAI calls are allowed only in worker jobs with explicit LLM responsibility:

- `brief.process` - optional/future conversion of operator text into structured search context
- `analysis.run` - produces community-level summaries and relevance notes
- `engagement.detect` - optional operator-approved engagement drafting from compact community samples

The seed-first discovery path does not require OpenAI. OpenAI calls are not allowed in API request
handlers, seed resolution, discovery, expansion, community snapshots, collection, engagement
scheduling, or sending.

## Developer Workflow

The repository provides a local `git ci` convenience command for small solo-operator commits:

```powershell
git ci "commit message"
```

It stages all changes with `git add -A` and commits them. The alias is configured in local Git
config and delegates to `scripts/git-ci.ps1`.

GitHub and VPS deployment use the workflow described in `wiki/spec/deployment.md`:

- branch pushes and pull requests run Ruff, pytest, and a Docker build
- the VPS deploy checkout is reset-only and follows `origin/main`
- coding agents on the VPS work in separate checkouts or worktrees on `agent/*` branches
- application secrets remain in local/VPS `.env` files and are excluded from Docker build context

## Context Fragmentation

Agent-facing docs and modules must stay cheap to route through:

- `wiki/index.md` is the routing table, not a full design document.
- Top-level specs stay under roughly 300 lines and link to focused shards for detailed endpoint,
  workflow, prompt, or rollout contracts.
- Plans stay under roughly 200 lines. Larger work is split into slice plans.
- `wiki/log.md` remains append-only; agents normally search its headings instead of reading the full
  history.
- Production files should stay under roughly 800 lines and tests under roughly 1,000 lines. When a
  touched file is already over the cap, new feature-sized work should include a cohesive extraction
  or be preceded by a refactor slice.
- Local agent worktrees, caches, pytest temp directories, sessions, data volumes, and env files are
  outside the project context and must stay ignored by Git and Docker.

---

## Data Flow

```text
Operator (Telegram bot)
  |
  | CSV upload, /seeds, /resolveseeds, /expandseeds
  v
api
  |
  | write seed_groups + seed_channels, enqueue work
  v
redis (RQ)
  |
  v
worker
  |
  +-- seed.resolve (Telethon username/entity resolution)
  |     -> communities with source=manual, status=candidate
  |
  +-- seed.expand (Telethon graph inspection)
  |     -> communities with source=expansion, status=candidate
  |     -> community_discovery_edges provenance
  |
  +-- community.snapshot after seed resolution or operator approval
  |     -> users, community_members, snapshots, collection_runs
  |
  +-- analysis.run after future analysis collection
        -> analysis_summaries

postgres
  ^
  |
bot lists candidates, jobs, accounts, and review actions through api
```

---

## Job Types

| Job | Trigger | Inputs | Does | Writes to |
|-----|---------|--------|------|-----------|
| `seed.resolve` | operator command | seed group id | Telethon resolves imported public usernames/links into real communities | `communities`, `seed_channels` |
| `telegram_entity.resolve` | direct bot text | intake id | Telethon classifies one public username/link as channel, group, user, or bot | `telegram_entity_intakes`, `communities`, `users` |
| `seed.expand` | operator command | seed group id | Telethon inspects resolved seeds; follows linked discussions, forwards, mentions, and Telegram links | `communities`, `community_discovery_edges` |
| `brief.process` | optional/future operator command | audience brief id | OpenAI-backed structured search-context extraction | `audience_briefs` |
| `discovery.run` | optional/future manual run | brief id or adapter query | source-adapter search for public Telegram seeds before resolution | `communities` candidates |
| `expansion.run` | optional/future manual run | community ids | generic Telethon expansion not anchored to a seed group | `communities` candidates |
| `community.snapshot` | seed resolution or manual review | community id | Telethon captures metadata + visible members; no raw message intake | `community_members`, `community_snapshots`, `collection_runs` |
| `collection.run` | engagement scheduler or manual engagement review | approved engagement community id | Telethon reads recent public messages for engagement detection; raw messages discarded by default | `community_members`, `community_snapshots`, `collection_runs`, `messages` opt-in only |
| `analysis.run` | after collection | collection run id | OpenAI summarizes themes, activity, relevance from compact analysis input | `analysis_summaries`, `collection_runs.analysis_status` |

Primary MVP chain:

```text
CSV seed import
  -> seed.resolve
  -> seed.expand
  -> operator review
  -> community.snapshot
  -> optional future analysis
```

Optional future chain:

```text
brief.process
  -> discovery.run
  -> optional seed-aware or generic expansion
  -> operator review
  -> community.snapshot or future analysis collection
  -> analysis.run
```

Snapshots may repeat on schedule after initial approval. Engagement collection has a separate,
faster cadence for approved engagement targets.

---

## Account Manager

Not a separate service. A utility module used by seed resolution, expansion, snapshot, collection,
and engagement workers.

```text
postgres: telegram_accounts table
  - stores account metadata and status

/sessions Docker volume
  - stores Telethon .session files (one per account)

acquire_account()
  - SELECT ... FOR UPDATE SKIP LOCKED on an available account
  - returns session file path
  - marks account as in_use

release_account(account_id)
  - marks account as available
  - updates last_used_at
  - clears lease_owner and lease_expires_at

on FloodWaitError
  - marks account as rate_limited
  - sets flood_wait_until = now + error.seconds

on AccountBannedError
  - marks account as banned
  - alerts operator via bot
```

5-10 accounts. Workers acquire one account per job, release on completion or error.

---

## Key Design Rules

- Bot talks to `api` only. Never directly to workers, Redis, Postgres, Telethon, or OpenAI.
- Workers are stateless. All state lives in Postgres. Sessions live in the volume.
- Alembic migrations are the implementation source of truth for schema changes. Keep migrations aligned with `wiki/spec/database.md`.
- Seed groups are the active intent object. Candidate discovery and review must preserve the seed group that produced each result.
- No business logic in collection worker. It fetches Telegram data, writes collection artifacts, and prepares capped analysis input only.
- OpenAI calls only in optional brief processing and analysis workers. Never in API handlers, seed resolution, collection, discovery, or expansion.
- TeleCatch is a reference only. It is not deployed as a service.
- Member collection is authorized research. Operator has explicit permission from Telegram team. Fields collected: user_id, username nullable, first_name nullable. Phone is never collected.

---

## Infrastructure Notes

- Redis memory footprint: approximately 50-100MB for queue + results at this scale.
- RQ worker: approximately 150MB. Can run multiple worker processes if needed.
- Postgres: approximately 150-300MB baseline.
- FastAPI + bot: approximately 100MB combined.
- Leaves 1GB+ headroom on a 2GB VPS for Telethon sessions and OS overhead.
- Telethon sessions: each active session holds approximately 5-20MB depending on dialogs cached.

---

## Open Questions

- How should seed-group candidate ordering be exposed in API responses?
- How to handle communities that become private after being added to the watchlist?
