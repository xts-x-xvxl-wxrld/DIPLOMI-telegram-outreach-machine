# Change Log

Append-only. Never edit existing entries.
Format: `## [YYYY-MM-DD] <type> | <short title>`
Types: spec | plan | code | refactor | fix | decision | question

---

## [2026-04-19] plan | Engagement operator controls

Planned a Telegram-native engagement control surface covering settings presets, topic controls,
manual join/detect jobs, candidate send queueing, and action audits. Noted backend API gaps for
join-job enqueueing and engagement action listing before the bot can expose the complete workflow.

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

## [2026-04-15] decision | Locked brief-to-discovery MVP design

Locked the next development slice around async audience brief processing followed by TGStat discovery.
Added `brief.process` as the job between API brief creation and `discovery.run`.
Allowed OpenAI calls only in `brief.process` and `analysis.run`; API handlers, discovery,
expansion, and collection remain non-LLM boundaries.
Decided TGStat discovery will use channel/chat search, post search, and mentions-by-channels with
deterministic ranking and match reasons.
Kept auto expansion off by default, Telegram bot as the MVP operator UI, raw message storage opt-in,
and MVP approve behavior as approve directly to monitoring.
Added audience brief, discovery, and bot specs plus the brief discovery slice implementation plan.
Filled the remaining indexed module specs for expansion, collection, analysis, and frontend with
baseline boundaries so the wiki index no longer points at missing files.

## [2026-04-15] code | Adapted queue and API contracts for brief processing

Added the `brief.process` queue payload and enqueue helper.
Changed brief creation so `POST /api/briefs` always enqueues `brief.process` with the
`auto_start_discovery` flag instead of enqueueing discovery directly.
Added a worker dispatch stub for `brief.process` and set discovery `auto_expand` defaults to false.
Updated queue payload tests for the new contract.
Verified with `python -m compileall backend bot tests` and `pytest -q` (10 passed).

## [2026-04-15] code | Implemented brief.process worker

Added the real `brief.process` worker implementation.
The worker reads `audience_briefs.raw_input`, calls OpenAI for structured extraction,
validates and caps brief fields, writes the structured arrays back to `audience_briefs`,
and enqueues `discovery.run` only after a successful commit when `auto_start_discovery = true`.
Added focused tests for normalization, invalid extraction behavior, and discovery enqueue ordering.
Verified with `python -m compileall backend bot tests` and `pytest -q` (15 passed).

## [2026-04-15] code | Implemented MVP Telegram bot shell

Added the Telegram bot runtime, standalone bot settings, backend API client, and concise
operator-facing message formatting.
Implemented `/start`, `/brief`, `/briefs`, `/job`, `/candidates`, `/approve`, `/reject`,
and `/accounts` as API-only bot commands.
Added BotFather token and API base URL environment variables to `.env.example`.
Added tests for bot config, API client authorization/payloads, error handling, and message
formatting.
Verified with `python -m compileall backend bot tests` and `pytest -q` (24 passed).

## [2026-04-15] code | Added environment placeholder files

Created a local `.env` file with placeholder values for Docker and bot runtime configuration.
Updated `.env.example` to mirror the same keys and section comments.
Confirmed `.env` is ignored by git while `.env.example` remains tracked as the template.

## [2026-04-15] code | Added manual seed CSV import

Added named manual seed groups as the TGStat-light MVP discovery path.
The API now imports CSV text into `seed_groups` and `seed_channels`, lists seed groups and channels,
and can start expansion from resolved seed-group communities.
The bot can import uploaded `.csv` documents, list seed groups with `/seeds`, and request
seed-group expansion with `/expandseeds`.
Updated the API, bot, database, discovery, expansion, queue specs, wiki index, and manual seed CSV
plan.
Verified with `pytest` (31 passed) and `ruff check .`.

## [2026-04-15] plan | Defined seed resolution contract

Created `wiki/plan/seed-resolution.md` and locked the manual seed field contract.
Seed rows now have explicit normalized fields, resolver statuses, and a separate `seed.resolve`
queue/API/bot boundary before expansion.
Updated the database, API, bot, expansion, queue, manual seed import plan, and wiki index specs.

## [2026-04-15] code | Added seed.resolve queue and bot surface

Added `seed.resolve` payloads, enqueue helper, worker dispatch stub, API route, bot client method,
`/resolveseeds` command, and operator formatting.
Extended seed channel statuses for resolver outcomes.
Verified with `python -m compileall backend bot tests`, `pytest -q` (35 passed), and
`ruff check .`.

## [2026-04-15] code | Implemented seed.resolve persistence

Added the fakeable seed resolution service, Telethon resolver adapter, and real `seed.resolve`
worker orchestration with account lease release handling.
Resolver results now create or update manual-source candidate communities, preserve existing
operator review statuses, and update seed row statuses for resolved, inaccessible, non-community,
invalid, and transient failure outcomes.
Expanded `/seeds` counts to show unresolved, resolved, and failed seed rows.
Verified with `pytest -q` (42 passed) and `ruff check .`.

## [2026-04-15] plan | Added seed batch expansion contract

Defined manual seed batch expansion as a first-class workflow.
`/expandseeds` should queue batch-scoped expansion from a `seed_group`, preserving the imported
batch context and graph evidence, instead of flattening resolved seeds into a generic arbitrary
community expansion request.
Added `wiki/plan/seed-batch-expansion.md` and updated the expansion, queue, API, bot specs, and wiki
index.

## [2026-04-15] code | Implemented seed batch expansion provenance

Added `community_discovery_edges` with seed-group, seed-channel, source-community, target-community,
and evidence fields for batch expansion provenance.
Added the `seed.expand` queue payload/enqueue helper, API wiring for
`POST /api/seed-groups/{seed_group_id}/expansion-jobs`, and worker dispatch with expansion account
lease release handling.
Implemented the fakeable seed batch expansion service that loads resolved seed rows, upserts
expanded candidate communities, preserves operator review statuses, writes readable batch-aware
match reasons, and skips duplicate provenance edges.
Verified with `pytest -q` (59 passed), `ruff check .`, and
`python -m compileall backend bot tests`.

## [2026-04-15] decision | Retired TGStat discovery direction

Removed TGStat from the active runtime contract and redirected discovery toward manual seed import,
public web-search adapters, Telegram-native search adapters, and seed graph expansion.
Removed the TGStat API setting, community source enum value, and active `communities.tgstat_id`
model field, with an Alembic migration to drop the old column.
Updated the discovery, architecture, queue, API, database, frontend, bot, audience-brief specs,
the brief discovery plan, wiki index, and LLM wiki.

## [2026-04-15] decision | Made seed groups the primary discovery intent

Reframed the MVP around example-community seed groups instead of audience briefs.
Seed groups now define operator intent; `seed.resolve` maps imported public usernames and links to
real communities, and `seed.expand` grows outward through linked discussions, forward sources,
Telegram links, and mentions.
Audience briefs remain optional/future context for filtering, web-search adapters, and analysis, but
they should not block the primary discovery workflow.
Added `wiki/plan/seed-first-discovery.md` and updated the architecture, discovery, expansion, queue,
API, bot, database, and audience-brief specs plus the wiki index.

## [2026-04-15] spec | Aligned supporting specs to seed-first workflow

Updated analysis and frontend specs so community review and summaries can be grounded in seed-group
context, with audience briefs treated as optional future context.
Marked the old brief discovery slice plan as superseded by the seed-first discovery plan.

## [2026-04-15] change | Bare seed collection path

- Paused expansion as the operator-facing next step after seed import.
- Added a bare seed collection plan.
- Implemented `collection.run` for metadata and visible member persistence with analysis skipped.
- Updated `seed.resolve` to queue collection for resolved seed communities.

## [2026-04-15] code | Built Telegram bot control-surface UX

Added a richer seed-first Telegram bot UX with persistent main-menu buttons, inline seed-group
actions, paged seed-channel and candidate views, inline approve/reject review controls, community
detail drill-down, manual collection triggers, and refreshable job status cards.
Added seed-group detail and seed-group candidate aggregation API reads to support the bot cleanly.
Updated the bot and API specs, indexed the new plan and `bot/ui.py`, and verified with
`pytest -q` (76 passed) and `ruff check .`.

## [2026-04-15] config | Prepared local bot runtime environment

Filled the local `.env` bot-to-API shared token with a generated secret and made the Telegram member
import cap explicit with the default value from `.env.example`. Telegram developer application
credentials still need operator-provided `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` before Telethon
resolution and collection jobs can run end to end.

## [2026-04-16] ops | Fixed CI package installation

Made setuptools package discovery explicit for the flat repository layout so CI can run
`python -m pip install -e ".[dev]"` without accidentally trying to package wiki or migration
directories. Updated the Dockerfile to copy installable packages before the editable install and
recorded the focused CI packaging plan.

## [2026-04-15] code | Added member access and account onboarding

Added a safe `GET /api/communities/{community_id}/members` API over persisted visible members,
Telegram bot `/members` and `/exportmembers` commands, and a local Telethon session onboarding
script that registers `telegram_accounts` rows.
Updated the API, bot, account manager specs, wiki index, and member access plan.

## [2026-04-16] docs | Added Telegram account safety runbook

Documented operational safety guidance for dedicated Telethon accounts, including read-only usage,
session-file handling, `FloodWait` recovery, banned/deauthorized account handling, and a recommended
two-account starter pool. Added onboarding commands and health checks to the member access plan.

## [2026-04-16] config | Fixed local Docker DNS for Telegram

The local Docker resolver mapped `api.telegram.org` to `109.239.191.125`, which served a certificate
for `essential.hiaware.com` and crashed the bot on startup with TLS hostname verification errors.
Added explicit public DNS resolvers to the `bot` and `worker` services, documented the local runtime
constraint, and added a focused plan for the DNS fix.

## [2026-04-16] code | Added seed CSV helper

Added `scripts/make_seed_csv.py` to generate bot-ready seed CSV files from public Telegram usernames
or links, using the same seed normalization rules as the API importer.
Updated the VUZ seed example to the accepted CSV header shape and documented the helper in the bot
spec, manual seed import plan, wiki index, and a focused helper plan.

## [2026-04-16] code | Added direct Telegram handle classification

Added direct bot text intake for public Telegram usernames and links. The API now records
`telegram_entity_intakes` rows and queues `telegram_entity.resolve`; the worker resolves through
Telethon and saves channels/groups to `communities` or users/bots to `users`.
The bot also exposes `/entity <intake_id>` to inspect the saved classification result.
Updated the API, bot, database, queue specs, wiki index, and direct intake plan.

## [2026-04-16] code | Added bot operator allowlist onboarding

Added optional `TELEGRAM_ALLOWED_USER_IDS` parsing, a public `/whoami` command, and a bot access gate
that returns the sender's Telegram user ID to unauthorized users for operator onboarding.
Updated the bot spec, environment template, wiki index, and bot operator access plan.

## [2026-04-16] ops | Added GitHub and VPS deployment pipeline

Added CI for Ruff, pytest, and Docker build; a production VPS deploy workflow that uses strict SSH
host-key checking; reset-only deploy and branch-scoped agent worktree scripts; and `.dockerignore`
protection for secrets and local runtime files.
The deploy path builds app images, waits for Postgres, applies Alembic migrations, and then restarts
Docker Compose.
Documented the two-way GitHub workflow in README, deployment spec, pipeline plan, architecture, and
wiki index.

## [2026-04-16] ops | Required per-slice agent commits

Added a Git freshness protocol requiring agents to commit and push after every completed wiki or
codebase change slice, while checking `git status` first to avoid bundling unrelated dirty work or
secrets.
Updated AGENTS.md, README, the deployment spec, and the VPS pipeline plan.

## [2026-04-16] fix | Fixed deploy workflow YAML

Indented the VPS deploy heredoc terminator inside the workflow `run` block so GitHub Actions can
parse `.github/workflows/deploy-vps.yml` on push and workflow-run events.

## [2026-04-16] ops | Pointed VPS deploy workflow at staging

Changed the GitHub Actions deploy environment from `production` to `staging` and updated the README,
deployment spec, wiki index, and VPS pipeline plan to describe staging environment secrets and
staging deploys.

## [2026-04-16] fix | Added deploy secret diagnostics

The staging deploy workflow failed in the `Install SSH key` step before any SSH connection attempt,
which means a required staging environment secret was empty or unavailable. Replaced bare `test -n`
checks with explicit GitHub Actions error annotations naming the missing secret without printing
secret values.

## [2026-04-16] fix | Added VPS deploy preflight diagnostics

Added remote preflight checks to the staging deploy workflow for the deploy path, Git checkout,
VPS `.env`, Git, Docker, Docker Compose, and Docker user permissions so remote setup failures report
the missing server prerequisite directly.

## [2026-04-17] code | Added Telegram bridge for VPS bots

Added an optional Telegram bridge that saves allowlisted plain-text bot messages to a JSONL inbox and
provides a small Bot API send script for VPS bots and Codex sessions to reply through Telegram.
Updated the bot spec, environment template, Docker bot volume, README, wiki index, and tests.

## [2026-04-18] fix | Removed Telegram bridge

Removed the optional Telegram bridge because it added confusing coordination semantics without a
clear operator benefit. The Telegram bot now returns to the seed-first control surface plus direct
public handle intake, and VPS agent communication is kept out of the bot runtime.

## [2026-04-17] fix | Restricted staging Postgres exposure

Changed Docker Compose so Postgres binds to `127.0.0.1:5432` instead of every public interface.
Updated the deployment spec and VPS pipeline plan to keep database access limited to Docker
networking and optional SSH tunnels.

## [2026-04-18] ops | Added VPS agent context and environment deploy gates

Added a redacted VPS agent context, status/log/deploy helper scripts, and an installer for
`/srv/tg-outreach`. Generalized the GitHub deploy workflow so staging can auto-deploy after CI while
staging and production can also be deployed manually through GitHub environments. Made Docker host
port bindings configurable so staging and production can coexist on one VPS without exposing
Postgres publicly. Documented narrow sudoers rules for status/log visibility without adding coding
agents to the Docker group.

## [2026-04-18] ops | Simplified GitHub deploy to staging only

Removed production as a GitHub Actions deployment target for now. The deploy workflow now uses only
the `staging` GitHub environment, while production remains documented as a reserved future VPS path.

## [2026-04-18] spec | Added community engagement module

Added an optional engagement module for operator-approved Telethon joins, topic detection, candidate
reply drafting, review, sending, and audit logs. The spec keeps outbound behavior separate from
collection and analysis, requires human approval in the MVP, forbids DMs and person-level scoring,
and documents future database tables, queue jobs, API routes, and account-manager purposes.

## [2026-04-18] spec | Expanded engagement implementation contracts

Expanded the engagement spec from a module outline into a concrete implementation contract. Added
status values, state transitions, service interfaces, worker preflights, Telethon adapter contracts,
API DTOs, idempotency rules, rate-limit rules, error mapping, scheduler behavior, observability, and
minimum test expectations. Updated the database spec draft fields and marked the wiki contract slice
complete in the engagement plan.

## [2026-04-19] code | Added engagement schema foundation

Added engagement status enums, SQLAlchemy models, and an Alembic migration for community engagement
settings, account memberships, topics, candidate replies, and outbound action audit logs. Added
schema tests for enum values, defaults, uniqueness constraints, indexes, and PostgreSQL DDL
compilation. Marked the schema foundation slice complete in the engagement plan.

## [2026-04-19] code | Added engagement queue contracts

Added queue payloads, enqueue helpers, retry policies, deterministic engagement job IDs, and worker
dispatch stubs for `community.join`, `engagement.detect`, and `engagement.send`. Added queue
contract tests for JSON serialization, queue placement, job IDs, and dispatcher recognition. Marked
the queue contracts slice complete in the engagement plan.

## [2026-04-19] code | Extended account manager purposes for engagement

Updated the account manager purpose contract to accept `entity_intake`, `engagement_join`, and
`engagement_send` in addition to existing expansion and collection leases. Added tests locking the
supported purpose set, engagement-purpose validation, unknown-purpose rejection, and banned-account
release mapping. Marked the account manager extension slice complete in the engagement plan.

## [2026-04-19] code | Added engagement settings and topics API

Added the engagement API router, response/request schemas, and a community engagement service for
per-community settings and operator-defined topics. Settings now return a disabled synthetic view by
default, enforce MVP approval and reply-only safety gates, and reject joining/posting for
unapproved communities. Topic creation and updates normalize keywords, preserve guidance/example
fields, reject active topics without triggers, and block unsafe guidance. Updated the wiki index and
marked the API settings and topics slice complete.

## [2026-04-19] code | Added community join worker

Implemented the `community.join` worker, engagement membership state helpers, account selection for
requested/assigned/joined accounts, and a fakeable Telethon engagement adapter. Join attempts now
write audit actions, update durable membership state, release account leases with success,
rate-limited, banned, or error outcomes, and skip safely when joins are not enabled. Added worker
tests for success, already joined, inaccessible communities, FloodWait, banned sessions, and
disabled joins. Marked the join worker slice complete in the engagement plan.

## [2026-04-19] code | Added engagement detection worker

Implemented `engagement.detect` as a no-send worker that loads active engagement settings/topics,
reads compact recent collection samples or opt-in stored messages, applies keyword prefiltering
before model calls, validates structured draft output, and creates capped engagement candidates.
Added candidate creation, phone redaction, reply safety validation, compact model-output storage,
and active-candidate dedupe helpers. Wired worker dispatch and the engagement queue runner, added
`OPENAI_ENGAGEMENT_MODEL`, and covered no-signal, draft-created, and duplicate-skip paths with
tests. Marked the detection worker slice complete in the engagement plan.

## [2026-04-19] code | Added engagement review API and bot controls

Added candidate review service transitions and API routes for listing pending engagement replies,
approving candidates, and rejecting candidates. Approvals now validate expiry and final reply text
while recording reviewer metadata; rejections record reviewer metadata without sending or enqueueing
Telegram work. Added bot commands and inline controls for reviewing engagement candidates, plus
focused tests for API contracts, bot client calls, formatting, and callback data. Marked the review
API and bot controls slice complete in the engagement plan.

## [2026-04-19] code | Added engagement send worker

Implemented the `engagement.send` worker for approved public replies. The worker now verifies
approval, expiry, posting settings, reply-only requirements, joined membership, final text safety,
and community/account send limits before using the membership account. It writes idempotent
`engagement_actions`, stores exact outbound text and sent Telegram message IDs, skips safely for
rate limits and stale reply targets, maps Telethon account errors through account-manager release
outcomes, and fails closed for orphaned queued actions that cannot be confirmed. Added focused send
worker tests and wired dispatcher support to the live worker.

## [2026-04-19] code | Added engagement detection scheduler

Added a lightweight engagement scheduler process that selects communities with enabled engagement
settings, requires a recent completed collection run, skips active candidates, respects quiet hours,
and enqueues only `engagement.detect` jobs with hourly deterministic job IDs. Added a manual
detection helper with a distinct job ID prefix for future operator-forced runs, Docker Compose
scheduler wiring, scheduler configuration, and focused tests for target filtering and quiet hours.
Updated the engagement plan and architecture/index wiki entries.

## [2026-04-19] code | Wired manual engagement job API endpoints

Added API request DTOs and routes for manual `engagement.detect` jobs and approved-candidate
`engagement.send` jobs. The manual detection endpoint verifies the community exists before using
the manual detect queue helper, and the send-job endpoint verifies the candidate exists and is
approved before enqueueing. Telethon work remains in the workers. Added focused API tests for
enqueue payloads, missing communities, approved sends, and unapproved send rejection.

## [2026-04-19] code | Closed engagement operator API gaps

Added the `community.join` API enqueue endpoint and engagement action audit listing endpoint for the
operator bot control surface. Candidate listing now accepts `community_id` and `topic_id` filters,
and action listing supports community, candidate, status, action type, limit, and offset filters
without exposing account phone numbers or person-level data. Added focused API tests for join
enqueue success, missing communities, queue failure, action audit shape, pagination filters, and
candidate filters.

## [2026-04-19] code | Built engagement bot foundation controls

Extended the bot API client with engagement settings, topic management, join, manual detection,
send-job, action audit, and filtered candidate methods. Added compact engagement formatters for the
home summary, settings, topics, queued jobs, audit rows, and approved candidate send next steps.
Expanded callback helpers for all planned `eng:*` namespaces, safe preset and paging markups, and
an Engagement reply-keyboard entrypoint. Added focused bot client, formatting, and callback tests;
the full Python suite now passes.
