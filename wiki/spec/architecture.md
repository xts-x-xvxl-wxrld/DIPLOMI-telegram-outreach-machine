# Architecture Spec

## Overview

Single-operator Telegram community discovery and monitoring app.
Deployed on a VPS (2-4GB RAM) using Docker Compose.
Fully async job pipeline. Telegram bot as prototype operator UI.

---

## Docker Compose Services

| Service | Image | Role |
|---------|-------|------|
| `api` | FastAPI | REST API — receives bot commands, enqueues jobs, serves results |
| `worker` | Python + RQ | Job runner — discovery, expansion, collection, analysis |
| `bot` | Python + python-telegram-bot | Operator UI — commands, candidate review, debug logs |
| `redis` | redis:alpine | Job queue + RQ result backend |
| `postgres` | postgres:16 | Primary datastore |

All services share one Docker network. Only `api` and `bot` communicate over HTTP. Workers talk directly to Postgres and Redis.

---

## Repository Layout

Implementation should use this layout unless a later spec explicitly changes it:

```text
backend/
  api/            # FastAPI routes, dependencies, response schemas
  core/           # settings, logging, shared app utilities
  db/             # SQLAlchemy models, sessions, repositories
  queue/          # RQ connection, enqueue helpers, job metadata helpers
  workers/        # discovery, expansion, collection, analysis, account manager
bot/              # Telegram bot operator UI
alembic/          # database migrations
scripts/          # local developer workflow helpers
docker-compose.yml
.env.example
```

Shared contracts should live in `backend/` and be imported by both API and worker code. The bot should depend on HTTP responses, not internal Python modules.

---

## Runtime Configuration

Use these environment variable names:

| Variable | Used by | Purpose |
|---|---|---|
| `DATABASE_URL` | api, worker | PostgreSQL connection string |
| `REDIS_URL` | api, worker | Redis/RQ connection string |
| `BOT_API_TOKEN` | api, bot | Internal bearer token for bot-to-API calls |
| `OPENAI_API_KEY` | worker | OpenAI API access for analysis jobs |
| `TGSTAT_API_TOKEN` | worker | TGStat API access for discovery jobs |
| `TELEGRAM_API_ID` | worker | Telegram API ID for Telethon |
| `TELEGRAM_API_HASH` | worker | Telegram API hash for Telethon |
| `SESSIONS_DIR` | worker | Mounted Telethon session directory |
| `COLLECTION_INTERVAL_MINUTES` | worker | Scheduler interval for monitored communities; default 60 |

Secrets must not be committed. `.env.example` may list variable names with empty values.

## Developer Workflow

The repository provides a local `git ci` convenience command for small solo-operator commits:

```powershell
git ci "commit message"
```

It stages all changes with `git add -A` and commits them. The alias is configured in local Git
config and delegates to `scripts/git-ci.ps1`.

---

## Data Flow

```
Operator (Telegram bot)
  │
  └─ HTTP ──▶ api
                │
                └─ enqueue ──▶ redis (RQ)
                                  │
                            ┌─────▼──────┐
                            │   worker   │
                            │            │
                   ┌────────▼──┐   ┌─────▼──────┐
                   │ discovery │   │ expansion  │
                   │ (TGStat)  │   │ (Telethon) │
                   └────────┬──┘   └─────┬──────┘
                            │            │
                   ┌────────▼────────────▼──────┐
                   │      collection            │
                   │  (Telethon batch poll)      │
                   └────────────┬───────────────┘
                                │
                   ┌────────────▼───────────────┐
                   │        analysis            │
                   │      (OpenAI API)           │
                   └────────────┬───────────────┘
                                │
                           postgres
                                │
                   bot polls / notifies operator
```

---

## Job Types

| Job | Trigger | Inputs | Does | Writes to |
|-----|---------|--------|------|-----------|
| `discovery` | operator command | audience brief id | TGStat keyword/channel/post search | `communities` (candidates) |
| `expansion` | after discovery or manual | community id(s) | Telethon inspects seeds; follows forwards, mentions, t.me links | `communities` (more candidates) |
| `collection` | scheduler (30-60 min) | watchlist community ids | Telethon batch polls messages + member list; raw messages discarded by default | `community_members`, `community_snapshots`, `collection_runs`, `messages` (opt-in only) |
| `analysis` | after collection | collection run id | OpenAI summarizes themes, activity, relevance from compact analysis input | `analysis_summaries`, `collection_runs.analysis_status` |

Jobs are chained: discovery → expansion → (operator review) → collection → analysis.
Collection and analysis repeat on schedule after initial approval.

---

## Account Manager

Not a separate service. A utility module used by expansion and collection workers.

```
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

- **Bot talks to `api` only.** Never directly to workers, Redis, or Postgres.
- **Workers are stateless.** All state lives in Postgres. Sessions live in the volume.
- **Alembic migrations are the implementation source of truth for schema changes.** Keep migrations aligned with `wiki/spec/database.md`.
- **No business logic in collection worker.** It fetches Telegram data, writes collection artifacts, and prepares capped analysis input only.
- **OpenAI calls only in analysis worker.** Never in collection, discovery, or expansion.
- **TeleCatch is a reference only.** It is not deployed as a service.
- **Member collection is authorized research.** Operator has explicit permission from Telegram team. Fields collected: user_id, username (nullable), first_name (nullable). Phone is never collected.

---

## Infrastructure Notes

- Redis memory footprint: ~50-100MB for queue + results at this scale
- RQ worker: one process, ~150MB. Can run multiple worker processes if needed.
- Postgres: ~150-300MB baseline
- FastAPI + bot: ~100MB combined
- Leaves ~1GB+ headroom on a 2GB VPS for Telethon sessions and OS overhead
- Telethon sessions: each active session holds ~5-20MB depending on dialogs cached

---

## Open Questions

- How to handle communities that become private after being added to watchlist?
