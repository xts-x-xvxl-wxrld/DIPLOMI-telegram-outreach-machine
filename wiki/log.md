# Change Log

Append-only. Never edit existing entries.
Format: `## [YYYY-MM-DD] <type> | <short title>`
Types: spec | plan | code | refactor | fix | decision | question

---

## [2026-04-21] plan | Added search rebuild implementation plan

Added `wiki/plan/search-rebuild-implementation.md` to turn the open contract gaps in the search
rebuild spec into a staged implementation path. The plan sequences contract resolution, schema,
API, deterministic planning, Telegram entity search, normalization/ranking, bot review, seed
conversion, rerank/replay, controlled graph expansion, deferred post/web search, and later frontend
work. Linked the new plan from the wiki index.

## [2026-04-20] code | Added bot back and home navigation

Added shared inline navigation footers across bot discovery, engagement, community, job, member,
candidate, target, topic, prompt, settings, and pager markups. Child pages now expose `Back` to a
stable parent screen and `Home` to the top-level operator cockpit, while module cockpits expose
`Home`. Updated bot UI tests for the new navigation footer contract.

## [2026-04-20] fix | Fixed operator cockpit lint

Removed stale imports left behind by the operator cockpit reply-keyboard migration so CI Ruff lint
passes on the cockpit branch.

## [2026-04-20] code | Built operator cockpit and discovery cockpit

Implemented the full bot operator cockpit replacing the persistent reply keyboard. Added `op:*` and
`disc:*` callback constants, `operator_cockpit_markup()`, `discovery_cockpit_markup()`,
`discovery_seeds_markup()`, and `reply_keyboard_remove()` to `bot/ui.py`. Added
`format_operator_cockpit()`, `format_discovery_cockpit()`, `format_discovery_help()`, and
`format_help()` to `bot/formatting.py`. Updated `bot/main.py` with `_send_operator_cockpit()`,
`_send_discovery_cockpit()`, `_send_accounts()`, `_send_seed_groups()`, and `_send_help()` helpers.
Switched `/start` to clear the old keyboard and open the inline cockpit. Switched `/help` to show
help with cockpit navigation. Removed `main_menu_markup()` from all command responses. Routed
`op:home`, `op:discovery`, `op:accounts`, `op:help`, `disc:home`, `disc:all`, `disc:attention`,
`disc:review`, `disc:watching`, `disc:start`, `disc:activity`, and `disc:help` callbacks. Created
`tests/test_bot_handlers.py` with `/start`, `/help`, `/accounts`, `/seeds`, and all new cockpit
callback handler tests. Extended `tests/test_bot_ui.py` with cockpit markup and parser tests.
Updated `wiki/plan/bot-operator-cockpit.md` slices 2–5 to completed.

## [2026-04-20] spec | Reframed engagement cockpit around operator intent

Updated the bot engagement controls spec so the Telegram cockpit prioritizes operator intentions
instead of mirroring backend entities. Added Today, Review replies, Approved to send, Communities,
Topics, Voice rules, Limits/accounts, and Advanced as the primary navigation model. Added readiness
summaries, progressive disclosure rules, state-aware default actions, and human labels for backend
permissions. Updated the plan with an operator-intention navigation and readiness summary slice.

## [2026-04-20] spec | Defined engagement config editing model

Documented a reusable Telegram bot admin/settings editing model for engagement configuration. The
spec now requires explicit editable field allowlists, typed value parsing, preview or before/after
confirmation, backend-owned validation, audit/version history for outbound-affecting changes, and a
hard safety floor that editable prompts, topics, style rules, settings, and replies cannot weaken.
Updated the bot engagement controls plan with a config editing foundation slice.

## [2026-04-20] spec | Designed Telegram account pool separation

Added a dedicated Telegram account pool separation spec and implementation plan. The design splits
managed accounts into `search`, `engagement`, and `disabled` pools, maps every Telethon job purpose
to exactly one pool, defaults existing accounts to read-only search, and requires engagement joins
and sends to use only engagement-pool accounts. Updated account-manager, database, engagement, queue,
and wiki index docs with the new contract.

## [2026-04-20] code | Built engagement admin control plane

Completed the remaining engagement admin control-plane slices. Added prompt profile/version
storage, render-only prompt previews, scoped style rules, topic good/bad example APIs, candidate
reply revisions, prompt provenance on engagement candidates, and detection prompt assembly from the
active profile plus style/topic/message/community context. Expanded the Telegram bot with
`/engagement_admin`, target cards, prompt profile cards, style-rule cards, topic example commands,
and `/edit_reply`. Updated API, bot, database, engagement specs, and tests.

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

## [2026-04-19] code | Added engagement cockpit and send flow

Added `/engagement` as a bot cockpit that summarizes pending, approved, failed, and active-topic
counts from API client calls. Made `/engagement_candidates [status]` status-aware, exposed
`Queue send` only for approved candidates, added `/send_reply <candidate_id>` plus the matching
inline send callback, and kept approval separate from send enqueueing. Added focused fake-client bot
handler tests for the cockpit, approved send controls, approval next-step markup, and send job
queueing.

## [2026-04-19] code | Built engagement topic management controls

Added Telegram bot topic management for engagement operators. `/engagement_topics` now lists topic
cards with active state, trigger keyword previews, capped guidance, and inline toggles.
`/create_engagement_topic <name> | <guidance> | <comma_keywords>` parses the planned pipe syntax,
requires at least one trigger keyword before calling the API, and leaves unsafe guidance enforcement
to the backend service. `/toggle_engagement_topic <topic_id> <on|off>` and the matching inline
callback patch topic active state through the bot API client only. Added focused fake-client handler
tests for list, create, malformed parser input, command toggles, and callback toggles.

## [2026-04-19] code | Added engagement settings jobs and audit bot surface

Completed the remaining engagement operator bot controls for community settings, manual jobs, and
audit review. `/engagement_settings` now renders disabled synthetic settings without creating rows,
`/set_engagement` applies safe presets, and community detail cards expose an Engagement button.
`/join_community` and `/detect_engagement` queue explicit backend jobs with refresh controls, while
the matching inline callbacks route only through the bot API client. Added `/engagement_actions`
with optional community filtering, capped outbound text cards, failed/skipped diagnostics, and
filter-preserving inline paging. Added focused fake-client handler tests plus UI parser/pager coverage.

## [2026-04-19] spec | Drafted engagement admin control plane

Added a new engagement admin control-plane spec and implementation plan. The design separates
engagement target intake from regular seed add/import, adds admin-editable OpenAI prompt profiles
and rendered prompt previews, makes topic good/bad reply examples and per-scope style rules
first-class controls, and requires editable candidate final replies before approval and send.
Updated the engagement spec and wiki index to point to the new control-plane docs.

## [2026-04-19] code | Added engagement target approval gate

Added the `engagement_targets` table, SQLAlchemy model, API schemas, target CRUD/list endpoints,
and a dedicated `engagement_target.resolve` queue job that reuses the Telegram entity resolver
without touching seed rows. Join, detection, and send workers now require an approved engagement
target with the matching `allow_join`, `allow_detect`, or `allow_post` permission before account,
OpenAI, or outbound work proceeds. Added focused schema, API, queue, service, and worker tests for
existing-community intake, public username intake, duplicate targets, target resolution, and
fail-closed worker gates.

## [2026-04-20] code | Built Telegram account pool separation

Added `telegram_accounts.account_pool` with `search`, `engagement`, and `disabled` values,
including the Alembic migration, SQLAlchemy model field, enum constants, and lease-selection index.
The account manager now maps every Telethon purpose to a required pool, includes
`engagement_target_resolve` as a read-only search purpose, filters both generic and explicit account
acquisition by pool, and excludes disabled accounts by construction. Engagement settings and joined
membership lookup now require engagement-pool accounts for public joins/sends, while onboarding
supports `--account-pool search|engagement` with search as the safe default. Added focused coverage
for pool defaults, routing, assigned-account validation, and onboarding; the full Python suite
passes.

## [2026-04-20] spec | Drafted bot engagement controls spec

Added a dedicated bot engagement controls spec and implementation plan for the next Telegram bot
engagement layer. The design covers engagement target management, prompt profile admin flows, style
rules, topic examples, editable reply revisions, advanced community settings, conversation-state
editing, callback namespaces, API dependencies, and safety/testing contracts. Updated the bot spec
and wiki index to point to the new docs.

## [2026-04-20] spec | Listed missing engagement menu controls

Updated the bot engagement controls spec with a current menu gap inventory. The inventory separates
already exposed engagement controls from missing daily review, target, prompt, topic, style,
community, and cross-cutting admin UX controls, then names the recommended next menu slice.
Updated the matching implementation plan with the same known gaps.

## [2026-04-20] code | Built bot engagement intention navigation

Completed bot engagement controls Slice 2. `/engagement` now exposes intention-first entries for
today, review replies, approved-to-send replies, communities, topics, recent actions, and admin.
`/engagement_admin` now exposes communities, topics, voice rules, limits/accounts, and advanced
controls, with small landing cards for limits/account lookup and advanced prompt/audit routes.
Candidate, engagement target, and community settings cards now show readiness summaries before raw
IDs and fields, and candidate cards list state-relevant next actions. Added focused bot UI,
formatting, and handler tests.

## [2026-04-20] spec | Drafted bot operator cockpit spec

Added a dedicated top-level bot operator cockpit spec and implementation plan. The design replaces
the persistent reply-keyboard menu with an inline `/start` cockpit for Discovery, Engagement,
Accounts, and Help, adds an `op:*` callback namespace, keeps slash commands as durable shortcuts,
and documents how to clear the old Telegram reply keyboard during rollout. Updated the bot spec and
wiki index to point to the new docs.

## [2026-04-20] spec | Expanded discovery cockpit navigation

Updated the bot operator cockpit spec with a nested Discovery cockpit: Start search, Needs setup,
Review communities, Watching, Recent jobs, and Help. The update adds operator-facing discovery
vocabulary, `disc:*` callback guidance, readiness summaries for searches, example communities, and
suggested communities, plus first-slice implementation and testing expectations.

## [2026-04-20] code | Built bot engagement target controls

Completed bot engagement controls Slice 3. The Telegram bot now supports target status filters,
target detail cards, target resolution, rejection, archive, join/detect permission toggles,
target-scoped join jobs, and target-scoped detection jobs. Target approval and permission changes
show before/after permission state, while rejected and archived targets display all permissions off.
Added `GET /api/engagement/targets/{target_id}` plus focused API-client, UI parser, formatting,
handler, and engagement API tests.

## [2026-04-20] spec | Refined discovery cockpit labels

Updated the Discovery cockpit proposal to use `Needs attention` and `Recent activity`, added an
action-biased `Next:` line for the Discovery home card, and expanded `Start search` into a small hub
with New search, Add examples to existing search, All searches, and CSV format. Adjusted the
`disc:*` callback guidance and tests to match the refined labels.

## [2026-04-20] spec | Expanded bot engagement slice contracts

Expanded the bot engagement controls spec with detailed implementation contracts for slices 4
through 10: config editing foundation, candidate detail and revisions, prompt profile admin
controls, topic examples and style rules, advanced community settings, admin permission boundaries,
and release documentation with broader test wrap-up. Aligned the matching plan heading for the
release slice.

## [2026-04-20] code | Built bot config editing foundation

Completed bot engagement controls Slice 4. Added a reusable bot config-editing foundation with
explicit editable field metadata, typed parsers, per-operator pending edit state, 15-minute expiry,
preview/save/cancel rendering, and compact `eng:edit:*` callbacks. Wired the first concrete guided
flow into `/edit_reply <candidate_id>`, while preserving the existing pipe-command edit path.
Added focused tests for parser behavior, pending edit scoping and expiry, callback parsing, guided
reply-edit preview/save/cancel, and operator isolation.

## [2026-04-20] spec | Clarified engagement instructions and monitoring

Expanded the engagement spec with an operator-facing instruction model for the message-generation
agent and a monitoring/send-timing model for scheduled detection. The contract now states that
engagement watches approved public surfaces through collection artifacts, drafts from durable prompt
profiles/topics/style rules, prefers no reply when the moment is weak, and sends only through
approval, quiet-hour, membership, reply-only, and rate-limit preflights. Updated the community
engagement plan with the completed documentation slice.

## [2026-04-20] spec | Refined engagement prompt inputs and timing

Refined engagement instructions so topic guidance has two user-facing values: what conversation to
look for and what position to take. Style rules now answer how the account should sound in the
community. Draft generation should avoid broad past-message batches and use community summary,
topic guidance, style rules, selected source post or trigger excerpt, and reply context when needed.
Monitoring now prefers post-join trigger messages that are 15 to 60 minutes old, with keyword and
negative-keyword matching treated as opportunity selection rather than authorization to send.

## [2026-04-20] spec | Defined engagement detection contracts

Expanded the engagement spec with concrete detection contracts for the next implementation slices:
stable skip reasons, normalized detection samples, deterministic trigger selection, timing gates,
post-join filtering, bounded trigger records, lean draft model input, and structured output
validation. Updated the community engagement plan with a completed detection-contract slice.

## [2026-04-20] spec | Strengthened timely reply opportunities

Renamed the engagement-domain concept from vague candidates to reply opportunities while preserving
legacy `engagement_candidates` and `candidate_id` implementation names for compatibility. Added the
collection-versus-detection distinction, a freshness SLO, reply deadlines, collection-completion
detection cadence, single-source-post draft input, opportunity-level strength/timeliness/value
fields, and operator notification rules. Added the timely reply opportunities plan and updated the
wiki index.

## [2026-04-20] spec | Defined engagement collection batches

Expanded the collection, engagement, and queue specs with an engagement collection mode. Approved
engagement communities now have a contract for pulling every new visible message since the last
checkpoint, recording checkpoint ranges, exposing exact `engagement_messages` batches or stored
message rows for detection, and queueing `engagement.detect` with `collection_run_id` after
collection commits. Detection now prefers the exact collection-run batch before falling back to
stored messages or sampled artifacts.

## [2026-04-21] spec | Engagement embedding matching selector

Added `wiki/spec/engagement-embedding-matching.md` to define cached semantic topic matching for
engagement detection. Added `wiki/plan/engagement-embedding-matching.md` with rollout slices for
settings, cache schema, service integration, detector rollout, and evaluation. Updated the
engagement spec and wiki index to point future detector work at the embedding selector contract.

## [2026-04-21] code | Renamed discovery collection to community snapshots

Renamed the discovery-side collection worker, queue job, bot controls, and API endpoints to
community snapshots while keeping `collection.run` reserved for engagement collection. Updated the
discovery, collection, queue, API, bot, database, and account-pool specs so discovery stores
community snapshots and engagement owns message collection.

## [2026-04-21] code | Aligned engagement detector for semantic matching

Resolved the main semantic-selector blockers before implementation. Active topics may now rely on
semantic profile text instead of mandatory trigger keywords, detector input uses one selected
`source_post` plus optional `reply_context`, joined-membership and post-join/replyable gates run
before drafting, detector calls are capped per run, and compact candidate metadata can retain
future `semantic_match` audit fields. Updated the engagement specs and embedding-matching plan to
match the new rollout contract.

## [2026-04-21] code | Added engagement embedding cache schema and service

Added Postgres-backed `engagement_topic_embeddings` and `engagement_message_embeddings` cache tables
with the matching Alembic migration and SQLAlchemy models. Implemented
`backend/services/engagement_embeddings.py` for semantic-profile/message text normalization, hashing,
batched OpenAI embedding calls, cache reuse, cosine similarity scoring, stable top-K semantic match
selection, and expired message-cache cleanup. Added focused schema and service tests, and updated
the database and embedding-matching wiki specs plus the index entries for the new implementation
roots.

## [2026-04-21] code | Integrated semantic engagement detector matching

Wired the cached semantic selector into `engagement.detect` behind
`ENGAGEMENT_SEMANTIC_MATCHING_ENABLED`. The detector now runs membership/replyable/dedupe gates
before semantic scoring, sends selected semantic trigger posts into the existing draft model, keeps
keyword fallback for keyword-backed topics during rollout, caps detector calls per community run,
and stores compact semantic-match metadata with reply opportunities. Added detector tests for the
semantic path, no-match skips, keyword fallback, and detector-call caps.

## [2026-04-21] code | Added semantic matching observability fixtures

Added aggregate semantic selector and detector observability for cache hits/misses, created
embedding rows, deterministic rejections, below-threshold skips, selected semantic matches, avoided
detector calls, and semantic-created reply opportunities. Added structured selector/detector log
records and a sanitized JSONL evaluation fixture with validation tests for threshold tuning.

## [2026-04-21] code | Added semantic rollout review surface

Added the Slice 5b aggregate rollout surface for semantic matching. The backend now summarizes
semantic-created reply opportunity outcomes by similarity band through
`GET /api/engagement/semantic-rollout`, and the bot exposes `/engagement_rollout [window_days]` for
operator review. The surface reports aggregate approval, rejection, pending, and expired counts
without exposing source messages, candidate IDs, sender identity, phone numbers, or person-level
scores.

## [2026-04-21] code | Added bot candidate detail and revision controls

Completed Bot Engagement Controls Slice 5. The backend now exposes engagement candidate detail,
revision history, explicit expire, and failed-candidate retry routes. The Telegram bot exposes
`/engagement_candidate`, `/candidate_revisions`, `/expire_candidate`, and `/retry_candidate`, plus
inline candidate detail, guided edit, revision, expire, and retry controls. Candidate send buttons
remain limited to approved candidates, and revision/detail views keep source excerpts capped.

## [2026-04-21] code | Added prompt profile admin bot controls

Completed the prompt profile admin controls slice. The Telegram bot now exposes prompt profile
detail, immutable version history, render-only preview, guided field editing, duplication,
activation confirmation, and rollback confirmation. Prompt template edits reject unapproved
variables such as sender identity before calling the API when possible, and focused bot API-client,
handler, and config-editing tests cover the new control surface.

## [2026-04-21] spec | Added clean-sheet Telegram search rebuild design

Added a new `wiki/spec/search-rebuild.md` page to capture a stronger future search architecture for
Telegram community discovery. The spec defines first-class search runs, structured query planning,
multi-surface retrieval across entity search, post search, graph expansion, and optional public web
search, plus evidence-based normalization, ranking, review, and promotion of strong hits into
seeds. Added the corresponding `wiki/plan/search-rebuild.md` planning page and linked both from the
wiki index.

## [2026-04-21] code | Added topic example and style rule bot controls

Completed Bot Engagement Controls Slice 7. The backend now exposes topic and style-rule detail
routes for the bot, while the Telegram bot adds topic detail, example removal, keyword updates,
guided topic-guidance editing, scoped style-rule lists, style-rule detail, style-rule creation, and
guided/toggle style-rule admin flows. Topic cards now clearly separate good examples from bad
examples and mark bad examples as avoid-copy guidance, and focused bot/API tests cover the new
controls.

## [2026-04-21] code | Added advanced community settings bot controls

Completed Bot Engagement Controls Slice 8. The Telegram bot now exposes
`/set_engagement_limits`, `/set_engagement_quiet_hours`,
`/clear_engagement_quiet_hours`, `/assign_engagement_account`, and
`/clear_engagement_account`, all implemented through the existing
community engagement-settings API while preserving
`reply_only=true` and `require_approval=true`. Settings cards now show
direct command hints for limits, quiet hours, and account assignment, and
assigned accounts render with masked-phone labels from
`GET /api/debug/accounts` when available. Focused bot handler and
formatting tests cover parsing, preserved safety fields, clearing flows,
and masked account display.

## [2026-04-21] code | Added engagement admin permission boundary

Completed Bot Engagement Controls Slice 9. The bot now supports a
transitional engagement-admin allowlist through `TELEGRAM_ADMIN_USER_IDS`,
hides admin-only buttons when it can identify a non-admin locally, and
rejects protected prompt/style/topic/target/community-setting mutations
before calling the API. Daily candidate review remains available to
ordinary allowlisted operators, and focused bot access, UI, config, and
handler tests cover the new boundary.

## [2026-04-21] spec | Recorded search rebuild contract gaps

Expanded `wiki/spec/search-rebuild.md` with implementation-readiness gaps for the future search
rebuild. The spec now calls out unresolved database, search-run, query-planning, adapter,
normalization, evidence, ranking, review, seed-conversion, API, queue, graph-expansion, and UI
contracts that should be settled before rewriting existing discovery code around the new search
model.

## [2026-04-21] docs | Wrapped bot engagement controls release docs and tests

Completed Bot Engagement Controls Slice 10. Refreshed the final bot engagement controls docs,
current menu-gap inventory, main bot command spec, API prompt-profile route spec, engagement admin
control-plane notes, and wiki implementation roots. Focused bot/engagement release coverage passed
with 281 tests, and the full repo suite passed with 385 tests after rerunning outside the sandbox's
Windows temp-directory restriction.

## [2026-04-21] plan | Added bot engagement controls follow-up slices

Updated `wiki/plan/bot-engagement-controls.md` with the remaining bot engagement control gaps after
the semantic engagement work. Added planned follow-up slices for risky-action confirmations, guided
edit entrypoints, prompt/topic/style creation flows, menu/progressive-disclosure polish, and the
deferred backend capability boundary.

## [2026-04-21] spec | Completed search rebuild contract resolution

Completed Search Rebuild Implementation Slice 0. Replaced the blocking open-contract section in
`wiki/spec/search-rebuild.md` with concrete first-slice contracts for statuses, reviews, evidence,
normalization, ranking, caps, API boundaries, queue jobs, graph-expansion gating, and bot-first
operator controls. Updated database, API, queue, bot, and plan docs so Slice 1 can start from a
locked core search schema.

## [2026-04-21] code | Added query-driven search core schema

Completed Search Rebuild Implementation Slice 1. Added search enums, SQLAlchemy models, Pydantic
schemas, and Alembic migration `20260421_0011_search_schema.py` for search runs, planner queries,
run-scoped candidates, compact evidence, and review audit rows. Focused schema coverage validates
defaults, uniqueness, nullable unresolved candidates, foreign keys, and PostgreSQL DDL compilation;
the full test suite passed with 399 tests.

## [2026-04-21] code | Added bot engagement safety confirmations

Completed Bot Engagement Controls Slice 11. Target approval, target posting-permission changes,
and community engagement account assignment/clearing now render confirmation cards and delay API
mutations until the admin confirms. Confirmation cards show before/after permission or masked
account state, and non-admin confirm callbacks are rejected before protected API calls. Focused bot
UI, formatting, handler, and access coverage passed with 153 tests.

## [2026-04-22] code | Added guided engagement edit entrypoints

Completed Bot Engagement Controls Slice 12. Target detail cards now expose admin-only guided target
note editing backed by `PATCH /api/engagement/targets/{target_id}`, and community settings cards
now expose guided edit buttons for posting limits, quiet-hour start/end, and assigned engagement
account. Settings saves reuse the current-settings merge path so `reply_only=true` and
`require_approval=true` stay enforced, with backend validation still owning bounds and account-pool
checks. Focused bot UI, config-editing, API-client, handler, and access coverage passed with 152
tests.

## [2026-04-22] code | Added bot engagement creation flows

Completed Bot Engagement Controls Slice 13. Added `/create_engagement_prompt`, an inline
prompt-profile create flow, topic-card good/bad example creation buttons, and a real guided
style-rule creation flow behind the existing `Create` button. Creation flows stay admin-only,
preview before saving when button-led, and use existing engagement API routes. Focused bot
config-editing, UI, API-client, and engagement-handler coverage passed with 151 tests; the full
repo suite passed with 410 tests.

## [2026-04-22] code | Polished engagement menu disclosure

Completed Bot Engagement Controls Slice 14. The daily `/engagement` menu now has a direct
`Settings lookup` route that lists approved resolved engagement targets and opens the existing
community settings card with inline buttons. Target cards now expose direct settings buttons when a
community is resolved, default target/prompt/topic/style cards are more compact and
operator-facing, and detail views still preserve raw IDs and audit fields. Readiness formatting now
uses backend-provided labels or concrete block reasons when present. Focused bot UI, formatting,
and engagement-handler coverage passed with 162 tests.

## [2026-04-22] code | Added backend engagement admin capabilities

Completed Bot Engagement Controls Slice 15. Added `GET /api/operator/capabilities` and backend
`ENGAGEMENT_ADMIN_USER_IDS` capability checks for protected engagement-admin mutation routes. The
bot now sends `X-Telegram-User-Id`, prefers backend capability decisions for admin hiding/rejection,
and falls back to `TELEGRAM_ADMIN_USER_IDS` only when backend capabilities are unconfigured or
unavailable. Focused bot access, API-client, engagement-handler, and engagement API coverage passed
with 159 tests.

## [2026-04-22] plan | Added context fragmentation protocol

Added `wiki/plan/context-fragmentation-protocol.md` to define agent reading limits, wiki/code size
caps, and a refactor backlog for oversized specs and core modules. Updated `AGENTS.md`,
`CLAUDE.md`, `.gitignore`, `.dockerignore`, `wiki/spec/architecture.md`, and `wiki/index.md` so
future agents route through smaller context slices and ignore duplicate local worktrees/temp dirs.

## [2026-04-22] refactor | Applied wiki and bot fragmentation slice

Converted oversized top-level specs into routing contracts with focused shards for API, database,
queue, bot, bot cockpit, engagement, bot engagement controls, engagement admin controls, search
rebuild, and engagement embedding matching. Split oversized plan files for bot engagement controls,
community engagement, engagement operator controls, and search rebuild implementation into shard
directories. Split bot message formatting and inline UI helpers into common, discovery, and
engagement modules while preserving `bot.formatting` and `bot.ui` compatibility exports. Updated
`wiki/index.md` and `wiki/plan/context-fragmentation-protocol.md` with the new shard and module
entrypoints.

## [2026-04-22] refactor | Split oversized backend and bot modules

Split `bot/main.py` into app, runtime, discovery handler, callback handler, engagement command, and
engagement workflow modules while preserving `bot.main` compatibility exports. Split
`backend/services/community_engagement.py` into domain modules for settings, targets, topics,
prompts, style rules, candidates, actions, and shared view types. Split the remaining oversized
backend production files: engagement API routes, SQLAlchemy models, and the engagement detection
worker. After the split, no `/backend` or `/bot` production file exceeds the 800-line soft cap.
Ruff passed for `backend` and `bot`; the full test suite passed with 423 tests.

## [2026-04-22] docs | Aligned wiki pointers after module split

Updated top-level bot, cockpit, engagement, admin control-plane, API, and database spec code maps to
point at the compatibility facades and shard modules created by the backend/bot fragmentation
refactor. Clarified the remaining engagement questions around oversized tests and facade import
compatibility.

## [2026-04-22] guardrail | Added fragmentation size check to CI

Added `scripts/check_fragmentation.py` and tests to enforce wiki, production, and test file size caps
for tracked files. Wired the guardrail into GitHub Actions before Ruff and pytest, documented the
enforcement in the context fragmentation plan and agent instructions, and linked the script from the
wiki implementation roots. The append-only wiki log remains exempt, and current oversized files are
grandfathered at fixed ceilings so they cannot grow before being split.

## [2026-04-22] spec | Defined engagement MVP testing readiness

Added a focused readiness plan for finishing engagement before staged Telegram testing. The plan
turns the collection/detection audit into implementation slices for the real `collection.run`
worker, exact `engagement_messages` batches, `collection_run_id` detection payloads, timely reply
opportunity fields, active collection scheduling, operator controls, and a staged Telegram runbook.

## [2026-04-22] docs | Split engagement readiness plan shards

Split the engagement MVP testing readiness plan into focused shard files for collection/detection,
timeliness/scheduling, and the operator runbook so the plan stays within the fragmentation guardrail
while preserving the staged testing contract.
## [2026-04-22] implementation | Engagement collection exact-batch detection slice

- Implemented `collection.run` orchestration with account lease cleanup, fakeable Telethon message collection, exact `analysis_input.engagement_messages` batches, checkpoints, optional raw-message storage, and visible-user activity updates.
- Extended `engagement.detect` payloads with optional `collection_run_id` and deterministic exact-batch job IDs, with detection preferring exact collection batches and skipping mismatched run/community pairs.
- Added collection, queue payload, and detection sample tests; full suite passed with 433 tests and fragmentation guard passed.
## [2026-04-22] implementation | Search API skeleton slice

- Added `backend/api/routes/search.py` and `backend/services/search.py` to create search runs, list run/query/candidate state, enqueue `search.plan` and `search.rank`, and record run-scoped candidate reviews without calling Telethon or OpenAI in the API layer.
- Extended `backend/queue/client.py` and `backend/queue/payloads.py` with `search.plan` and `search.rank` queue helpers for the Slice 2 API boundary.
- Added `tests/test_search_api.py`; `python -m pytest -q tests/test_search_schema.py tests/test_search_api.py` and `python scripts/check_fragmentation.py ...` passed.
## [2026-04-22] code | Complete engagement reply-opportunity timeliness slice

- Added `engagement_candidates` freshness/deadline fields plus Alembic migration `20260422_0012`.
- Detection now computes reply-opportunity timeliness from source-message timestamps and skips stale automatic opportunities.
- Approval/send freshness checks now use `reply_deadline_at`, and operator cards expose freshness plus review/reply deadlines.
## [2026-04-22] implementation | Refresh bot copy readability and button labels

- Added shared plain-text formatting helpers for headings, labeled fields, action blocks, and
  status markers so discovery and engagement cards read like operator-friendly summaries instead of
  raw field dumps.
- Refreshed high-traffic bot messages and inline buttons across discovery, engagement, review, and
  admin surfaces with concise emoji anchors, clearer verbs, and more scannable section ordering.
- Added `wiki/plan/bot-copy-readability-refresh.md`, updated the bot UX/formatting specs, and
  passed `python -m pytest -q tests/test_bot_formatting.py tests/test_bot_ui.py` plus
  `python scripts/check_fragmentation.py`.
