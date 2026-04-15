# Change Log

Append-only. Never edit existing entries.
Format: `## [YYYY-MM-DD] <type> | <short title>`
Types: spec | plan | code | refactor | fix | decision | question

---

## [2026-04-15] decision | Architecture finalized

Completed architecture brainstorm with operator. All key decisions recorded in spec/architecture.md.
Full decision log:
- Deployment: Docker Compose on 2-4GB VPS (DigitalOcean)
- Task queue: RQ + Redis (lightweight, sufficient for 5-10 Telethon accounts)
- Database: PostgreSQL
- Telegram accounts: 5-10, custom account manager (not TeleCatch containerized)
- Collection mode: batch poll every 30-60 min
- Analysis: OpenAI API
- Prototype UI: Telegram bot
- TeleCatch: reference only, not deployed as a service
- Member collection: user_id, username (nullable), first_name (nullable)
- Activity window: 90-day rolling, recalculated on every collection run
- Activity event types: messages posted, forwards, reactions, other attributable events
- Activity tiers: inactive (0 events), passive (1-4), active (5+)
- Multi-tenancy: single operator

## [2026-04-15] spec | Created architecture.md, database.md, index.md, log.md

Initial wiki scaffolding. Wrote architecture and database specs from brainstorm decisions.

## [2026-04-15] decision | Removed reaction lookup and message_reactions table

Getting reactor identity requires a separate Telethon API call per message per emoji type —
too expensive at scale (thousands of extra calls per collection run).
Removed message_reactions table entirely.
Reactions no longer contribute to community_members.event_count.
Activity events are now: messages posted, forwards, other attributable service events.
Aggregated reaction counts on messages are still available via message.reactions for
community-level analysis but are not stored or attributed to users.
Updated spec/database.md.

## [2026-04-15] decision | Normalized users table, cross-community membership tracking

Added `users` table as central registry for Telegram user identity (tg_user_id, username, first_name).
`community_members` now references `users.id` instead of storing identity fields per row.
Enables cross-community membership lookup and avoids duplicating user fields across communities.
Updated spec/database.md.

## [2026-04-15] decision | Raw message storage is opt-in per community

Default collection pipeline: fetch → tally activity counts → pass to analysis worker → discard.
Raw messages are only written to the `messages` table when `communities.store_messages = true`.
Reason: storing all messages by default is too data-intensive for a 2-4GB VPS.
Relevance detection uses TGStat API + in-memory processing + analysis_summaries instead.
Updated spec/database.md and spec/architecture.md to reflect this.

## [2026-04-15] spec | Created backend API, queue, and account manager contracts

Created spec/account-manager.md, spec/queue.md, and spec/api.md.
Added wiki/plan/backend-contracts.md.
Decided collection jobs must not pass raw message batches through Redis.
Added collection_runs as the durable boundary between collection and analysis:
collection writes compact capped analysis_input, analysis receives collection_run_id.
Updated spec/database.md, spec/architecture.md, and index.md.

## [2026-04-15] decision | Locked backend foundation before implementation

Locked initial repository layout, runtime environment variable names, Alembic migration policy,
and MVP status-field strategy.
PostgreSQL status fields remain text columns; Python enums and Pydantic schemas validate values.
Defined the initial collection_runs.analysis_input JSON envelope in spec/queue.md.
Updated plan/backend-contracts.md, spec/architecture.md, spec/database.md, and spec/queue.md.

## [2026-04-15] code | Scaffolded backend foundation

Added FastAPI app factory, API dependency/auth wiring, health/readiness routes,
bot-facing API route skeletons, SQLAlchemy models, Alembic configuration, initial schema migration,
RQ queue helper contracts, worker dispatch stubs, account manager lease helpers, Docker Compose,
project metadata, environment template, bot placeholder, and foundation tests.
Verified with `python -m compileall backend bot tests`, `python -c "from backend.api.app import create_app; app=create_app(); print(len(app.routes))"`,
and `pytest -q` (7 passed).

## [2026-04-15] code | Added local git ci workflow

Initialized the project as a Git repository and added a repo-local `git ci` convenience command.
The command stages all changes with `git add -A` and commits with the provided message.
Added `.gitignore`, `scripts/git-ci.ps1`, and `wiki/plan/git-ci.md`.
Updated the architecture spec and wiki index with the developer workflow helper.
