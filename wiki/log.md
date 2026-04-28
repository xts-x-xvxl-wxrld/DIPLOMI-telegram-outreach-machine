# Change Log

Append-only. Never edit existing entries.
Format: `## [YYYY-MM-DD] <type> | <short title>`
Types: spec | plan | code | refactor | fix | decision | question

---

## [2026-04-26] code | Engagement add wizard (5-step guided community setup)

Implemented the guided engagement add wizard per `wiki/spec/bot/engagement-add-wizard.md` and
`wiki/plan/engagement-add-wizard/`.

New files:
- `bot/engagement_wizard_flow.py` — wizard state machine, step routing, resume logic, launch
- `bot/engagement_commands_wizard.py` — `/add_engagement_target` command wiring
- `bot/formatting_engagement_wizard.py` — wizard step and summary card formatters
- `tests/test_bot_engagement_wizard.py` — 20 bot-conversation tests covering all 5 steps

Key changes:
- `ACTION_ENGAGEMENT_TARGET_ADD` callback now starts the wizard instead of legacy target create
- `ACTION_ENGAGEMENT_WIZARD = "eng:wz"` callback namespace with admin gate
- Wizard state stored in `PendingEditStore` using `entity="wizard"` and a `WIZARD_RETURN_STORE_KEY`
  in bot_data for nested topic-create return
- Topic "attachment" = `active=True` on selected topics + `flow_state['topic_ids']`; no DB migration
- Level → mode mapping: watching→observe, suggesting→suggest, sending→require_approval
- Permission collapse: `reply_only`/`require_approval` kept at server defaults; only `mode`,
  `allow_join`, `allow_post` set by the wizard
- Updated spec to clarify the pragmatic topic attachment approach
- CI: fragmentation guardrail, ruff, and 557 pytest tests all pass

---

## [2026-04-24] fix | Catch socket-level queue enqueue failures

- Broadened queue error normalization so non-duplicate enqueue failures such as connection-refused
  errors also surface as `QueueUnavailable` instead of bubbling as API 500s.
- Updated queue regression coverage to exercise a built-in connection error, matching the live
  target-resolve failure mode more closely.

## [2026-04-27] spec | Added bot engagement redesign build plan

Added `wiki/plan/bot-engagement-redesign.md` to guide the next implementation phase for the
Telegram-bot-exclusive engagement surface. The plan keeps the redesign codebase-native by centering
reply opportunities, blockers, approvals, runtime-generated suggestions, edited final replies, and
admin-vs-daily intent separation instead of introducing a generic campaign-style cockpit model.
`python3 scripts/check_fragmentation.py` passed locally after trimming `wiki/index.md` back to the
150-line cap; `ruff` and `pytest` still could not run here because those modules are not installed
in the current environment.

## [2026-04-26] spec | Clarified runtime-generated engagement reply model

Verified from the implementation that engagement reply text is generated at detection time from
live context, not authored as a fixed prewritten outbound message. Updated engagement, drafting,
frontend, and bot operator cockpit specs so they describe prompt-profile-driven runtime reply
generation, stored `suggested_reply` candidates, operator approval/edit into `final_reply`, and
send-time use of the approved final text without a second OpenAI call. `python3
scripts/check_fragmentation.py` passed locally; `python3 -m ruff check .` and `python3 -m pytest
-q` could not run because the current environment does not have the `ruff` or `pytest` modules
installed.

Followed up by tightening the bot engagement and engagement API/bot shards so the operator workflow
is described as Telegram-native review of runtime-generated reply opportunities, with explicit
`suggested_reply` to `final_reply` review/edit/send steps instead of campaign-style message authoring.

## [2026-04-24] fix | Normalize queue outages on engagement target resolve

- Wrapped Redis/RQ enqueue failures in `backend/queue/client.py` so `engagement_target.resolve`
  and other queue-backed actions raise `QueueUnavailable` instead of bubbling raw infrastructure
  exceptions as HTTP 500s.
- Added queue regression coverage for Redis-style enqueue failures while preserving duplicate job-id
  handling.
- This turns the bot-side `Resolve` failure from a misleading internal server error into a handled
  queue-backend outage signal that the API routes can return as 503.

## [2026-04-23] code | Search deferred surface contracts

- Added dormant contracts for `telegram_post_search` and `web_search_tme`, including post snippet
  caps, sender-identity filtering, source post metadata, web provider/cache policy, and public
  Telegram URL normalization.
- Planner now recognizes deferred search adapters and writes skipped query metadata instead of
  enqueueing unsupported retrieval work.
- Added focused tests for deferred surface privacy/normalization and planner skip behavior.

## [2026-04-22] fix | Restored bot module entrypoint

Fixed the Docker bot service entrypoint by making `python -m bot.main` call the polling
entrypoint instead of importing compatibility exports and exiting with code 0. Added a focused
entrypoint regression test and documented the operational fix in the wiki index and plan.
After staging exposed live update handling, moved pending-edit command cleanup into the access
runtime shard and added access-gate coverage so bot commands no longer raise after startup.

## [2026-04-22] docs | Added staged Telegram engagement runbook

- Added an operator-facing runbook for fake-adapter gates, controlled Telegram dry run,
  observe-only real-community testing, one reply-only send, expected evidence, and abort switches.
- Marked the staged runbook readiness slice complete and updated the wiki index shard description.

## [2026-04-22] fix | Restored CI lint pass

- Added a CI lint fix plan and index pointer.
- Marked grandfathered compact API schema declarations with targeted Ruff suppressions so the file does not grow past its guardrail ceiling.
- Made engagement review formatter facade exports explicit and removed an unused helper import.

## [2026-04-22] implementation | Telegram entity search adapter slice

- Added `search.retrieve` worker orchestration with search-pool account leasing, account release, query-level adapter failure handling, and ranking enqueue handoff when retrieval reaches terminal query states.
- Added Telegram entity retrieval persistence for resolved public communities, run-scoped candidate merging, compact evidence rows, per-query/per-run caps, and preservation of existing community operator decisions.
- Added a Telethon-backed `telegram_entity_search` adapter plus fakeable tests for successful hits, duplicate hits, inaccessible/non-community hits, flood waits, and partial failure.

## [2026-04-22] code | Added active engagement collection scheduler

- Extended the existing scheduler worker to run active engagement collection ticks alongside the fallback detection sweep.
- Added default `ENGAGEMENT_ACTIVE_COLLECTION_INTERVAL_SECONDS=600` and minute-bucketed `collection:engagement:{community_id}:{yyyyMMddHHmm}` job IDs.
- Covered due, recent, active, quiet-hour, disabled, missing-permission, duplicate, enqueue-failure, and queue contract paths in tests.

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
## [2026-04-22] impl | Deterministic search planner slice

- added `backend/workers/search_plan.py` for deterministic `search.plan` execution, query persistence, idempotent reuse, and retrieval enqueueing
- added `search.retrieve` queue payload/helper wiring plus search job dispatch coverage for planner, retrieve, and rank jobs
- added focused planner tests for simple queries, duplicate terms, empty-query failure handling, locale hints, and same-run idempotency

## [2026-04-22] implementation | Search candidate normalization and ranking slice

- added replayable `search_rank_v1` scoring in `backend/services/search_ranking.py`, including title/username, description, cross-query, cross-adapter, activity, prior rejection, and spam components
- wired `backend/workers/search_rank.py` into the job dispatcher so `search.rank` persists candidate scores, component explanations, ranking metadata, and completed run state from stored rows only
- tightened candidate listing tie-breakers for converted status and null-title ordering, and added focused ranking/worker tests

## [2026-04-22] implementation | Engagement operator staged-test controls

- Added target-scoped manual collection API/client controls with approval and detect-permission gates, plus recent collection-run status listing for operator verification.
- Wired bot commands and target-card next steps for collect-now and collection-run status while preserving join, detect, review, approve, send, and audit controls.
- Refreshed reply-review copy to say reply opportunity while keeping legacy candidate IDs visible; focused engagement operator, bot API/UI, bot handler, and engagement API tests passed.
## [2026-04-22] implementation | Bot account onboarding helper

- Added `/add_account <search|engagement> <phone> [session_name] [notes...]` as a bot-only command
  preparation helper that returns the local Docker onboarding command without collecting Telegram
  login codes, 2FA passwords, or session files.
- Added bot/backend onboarding command helpers and kept the existing `scripts/onboard_telegram_account.py`
  login flow local and interactive.
- Extended `/accounts` and `GET /api/debug/accounts` with account-pool counts and per-account pool
  labels while keeping phone numbers masked.

## [2026-04-23] fix | Add engagement cockpit button emojis

- Preserved emoji labels in engagement home and admin cockpit buttons instead of flattening them through shared button-label overrides.
- Added bot UI regression assertions for engagement cockpit emoji anchors.
- Passed `python -m pytest tests/test_bot_ui.py -q` and `python scripts/check_fragmentation.py`.

## [2026-04-23] fix | Publish bot start command

- Published Telegram bot commands on startup with `/start` first so fresh bot conversations expose a Start command entrypoint.
- Added a startup-command regression test with a fake Telegram bot.
- Passed `python -m pytest tests/test_bot_startup_commands.py tests/test_bot_handlers.py -q` and `python scripts/check_fragmentation.py`.

## [2026-04-23] fix | Tighten agent CI guidance

- Added local CI parity rules to agent guidance so slices run fragmentation, Ruff, and pytest before commit/push, with Docker build required for packaging/runtime changes.
- Added generated pytest scratch directory ignore patterns for Git and Docker context.
- Fixed fallback Telegram markup classes so bot UI tests pass when the real Telegram package is unavailable.
- Verified the staged slice with fragmentation, Ruff, and pytest; `docker build .` could not run because the local Docker Desktop daemon was unavailable.

## [2026-04-23] implementation | Search bot surface and seed conversion

- Added bot-first search commands, candidate cards, callback paging, run-scoped promote/reject/archive actions, and promoted-candidate seed conversion controls.
- Added `POST /api/search-candidates/{candidate_id}/convert-to-seed` with duplicate seed-channel reuse, `manual_seed` evidence, `convert_to_seed` review metadata, and converted candidate status.
- Added focused bot/API/service/UI regression tests for Slice 6 and Slice 7.
## [2026-04-23] fix | Move account onboarding into accounts cockpit

- Added accounts-cockpit inline buttons for adding `search` and `engagement` Telegram accounts.
- Routed those buttons to pool-specific `/add_account ...` usage instructions while keeping login
  codes, 2FA, and session files out of bot chat.
- Changed `/accounts` and `op:accounts` to use the accounts cockpit markup instead of the generic
  operator cockpit.

## [2026-04-23] implementation | Add VPS diagnostics bundle helper

- Verified staging log access on the VPS: `codex-ravil` and `claude-ravil` can use the sudo-gated
  status/log helpers as `deploy`; `codex-pink` is in `tg-outreach-dev` but this SSH key was not
  accepted for that account.
- Added scheduler and all-service support to the bounded VPS log helper.
- Added a non-secret diagnostics helper that saves status, container state, and bounded service logs
  under `/srv/tg-outreach/diagnostics`.
- Grandfathered the existing oversized `tests/test_queue_payloads.py` fragmentation debt so the
  guardrail can keep enforcing no-growth behavior.
- Made the diagnostics helper usable by non-Docker agent users through the already sudo-gated
  status/log helpers.
- Folded Docker log stdout/stderr together so piped all-service output keeps service sections
  readable.

## [2026-04-23] implementation | Search rerank replay metadata and graph expansion gate

- Implemented Slice 8 rerank observability by recording last rerank job metadata on search runs and preserving ranking component shape with replayable `search.rank` output.
- Implemented Slice 9 `search.expand` queue/API/worker plumbing with expansion-account leasing, promoted/resolved search-candidate roots, resolved manual seed roots, global rejection guards, compact graph evidence, and rank handoff.
- Added focused tests for search expansion service gates, queue payload/dispatch contracts, worker account release, API expansion job metadata, and ranking component metadata.

## [2026-04-23] implementation | Bot-driven Telegram account onboarding

- Added bearer-auth account onboarding API routes for Telethon login-code start and complete steps.
- Changed `/add_account` to start bot-based onboarding, consume/delete code and 2FA messages, and register the account after authorization.
- Mounted the shared Telegram sessions volume into the API service so bot-started sessions are available to workers.
- Updated account/API specs, plan, index, and focused onboarding tests.
- Verified with fragmentation, Ruff, pytest, and `docker build .` after starting Docker Desktop.

## [2026-04-23] implementation | Guided account cockpit onboarding

- Changed the accounts cockpit `Add search` and `Add engagement` buttons to start a guided phone,
  session-name, and notes flow before requesting the Telegram login code.
- Kept the direct `/add_account <pool> <phone> [session_name] [notes...]` command path for fast
  operator entry.
- Updated account onboarding plan/spec notes and focused bot handler coverage.

## [2026-04-23] fix | Simplify account onboarding prompts

- Reworked guided account onboarding prompts to show only the current requested value and a short example.
- Added skip buttons for optional account name and notes, with session filenames still normalized behind the scenes.
- Delayed cleanup of onboarding messages until successful flow completion, then deletes them after a short pause.

## [2026-04-24] implementation | Add step-by-step topic creation flow

- Replaced the guided topic create payload prompt with a five-step question flow covering topic
  name, guidance, trigger keywords, optional description, and optional negative keywords.
- Kept the existing confirmation/save step and /cancel_edit behavior, while storing wizard step
  state in the shared pending edit store.
- Left legacy inline /create_engagement_topic ... | ... | ... parsing available for direct command
  users, and updated the bot spec/plan shards to describe the new default flow.

## [2026-04-27] implementation | Engagement home hierarchy refresh

- Reworked the `/engagement` home copy to lead with pending approvals, separate ready-to-send work from needs-attention blockers, and spell out the review -> edit/approve -> send path.
- Reordered the engagement home inline keyboard so pending approvals is the first primary action, added a direct needs-attention queue button, and kept config/admin shortcuts secondary.
- Updated the engagement navigation spec plus focused formatting, UI, and handler tests for the new operator-first home surface.

## [2026-04-27] implementation | Reply opportunity queue refinement

- Reworked reply-opportunity queue headers and card copy around operator states such as `Pending approvals`, `Ready to send`, `Needs attention`, and `Expired opportunities`.
- Added the missing `expired` queue filter, preserved queue-specific back navigation from detail cards, and aligned list buttons with the new operator wording.
- Added lightweight within-page prioritization for pending/approved queues using freshness and deadline hints, plus focused test coverage for queue ordering and filter availability.

## [2026-04-27] implementation | Reply workspace detail view

- Split open reply-opportunity detail from the compact queue card so operators now see `Source context`, `Reply workspace`, and `Audit fields` sections in one place.
- Made generated suggestion and final reply render as explicitly separate fields, including a clear “matches the generated suggestion” state before any edit.
- Updated detail return paths after edit, expire, and retry so operators land back in the richer review workspace rather than the compact queue card.

## [2026-04-27] implementation | Blocked reply fix paths

- Enriched reply-opportunity detail views with community settings context so blocked send readiness can explain a concrete blocker without a backend schema change.
- Added `Blocked path` guidance for posting-disabled, not-joined, account/quiet-hours/rate-limit, failed-send, and expired states, with direct commands to the right fix surfaces.
- Added blocked-detail action buttons for community settings and recent engagement actions when a reply opportunity needs operator remediation.

## [2026-04-27] implementation | Reply-opportunity copy consistency

- Normalized operator-facing engagement wording around `reply opportunity`, `generated suggestion`, and `final reply` while keeping legacy `candidate` only for audit IDs and command compatibility.
- Renamed review/revision/send-adjacent copy so approval, revision history, and queued-send surfaces read as one coherent workflow.
- Updated the engagement formatting/navigation spec language to match the shipped Telegram bot vocabulary.

## [2026-04-27] implementation | Config surfaces by operator intent

- Reframed the engagement admin/config surface around operator questions such as allowed communities, detection topics, reply style, send safety, and drafting/diagnostics.
- Renamed the related formatter headers so targets, topics, style rules, prompt profiles, and settings read as intent-led setup surfaces instead of backend object lists.
- Kept the existing commands, callbacks, and admin gating intact while updating focused handler, UI, and formatting expectations plus the engagement navigation spec.

## [2026-04-27] docs | Task-first engagement cockpit blueprint

- Added a dedicated wiki shard for the preferred task-first engagement cockpit, centered on clear operator intentions, wizard-first setup, and daily-work-first navigation.
- Documented first-run, in-progress setup, daily operations, and all-clear states with concrete home-screen button layouts and copy rules for non-technical Telegram operators.
- Linked the new blueprint from the cockpit experience parent doc, bot spec shard list, and wiki index so future implementation work has a clear source of truth.

## [2026-04-27] docs | Retire operator cockpit v2 spec

- Replaced `wiki/spec/bot-operator-cockpit-v2.md` with a short superseded stub so historical links still resolve without leaving two competing cockpit directions active.
- Updated cockpit-experience and simplification companion references to point at the new task-first engagement cockpit shard instead of v2.
- Kept shared attention and navigation rules intact while removing the remaining active wording that treated v2 as the current home-dashboard source of truth.

## [2026-04-27] docs | Make task-first cockpit shard authoritative

- Marked `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md` as the sole active UX source of truth for the engagement cockpit.
- Narrowed `wiki/spec/bot-cockpit-experience.md` so it no longer defines competing home, navigation, or wizard-topology rules.
- Superseded the older combined `Needs attention` and `Home` footer contract in `wiki/spec/bot-cockpit-experience/attention-and-navigation.md`.
- Added an explicit override note to `wiki/spec/bot/engagement-add-wizard.md` so older wizard terms cannot silently overrule the newer cockpit contract.

## [2026-04-27] docs | Rewrite engagement wizard around two sending modes

- Rewrote `wiki/spec/bot/engagement-add-wizard.md` around the active task-first cockpit contract: `Target -> Topic -> Account -> Sending mode -> Final review`.
- Removed the old `Watching` / `Suggesting` / `Sending` wizard model and the detect-only setup path from the operator-facing flow.
- Defined the new operator-facing sending modes as `Draft` and `Auto send`, with `Draft` as the default and `Auto send` mapped to backend `auto_limited`.
- Locked `Auto send` as an immediate feature rather than a deferred one, so the implementation slice must remove the current backend guard that rejects `auto_limited`.
- Changed abandoned setup behavior from wizard resume to fresh restart, while still allowing idempotent reuse of durable backend rows behind the scenes.
- Aligned the engagement wizard plan shards and the active simplification notes with the new sending-mode wording.

## [2026-04-27] docs | Add explicit task-first cockpit callback contract

- Added an explicit callback namespace and screen-routing section to `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`.
- Defined the home-entry callbacks under `op:*` and the task-first surface families under `eng:*`.
- Documented the concrete routing contract for `Approve draft`, `Top issues`, `My engagements`, `Sent messages`, engagement detail, and wizard edit-entry points.
- Made early-exit return behavior explicit by requiring stored return context for draft-edit and issue-fix subflows.

## [2026-04-27] docs | Add task-first cockpit data contract

- Added a task-first cockpit data-contract section to `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`.
- Defined the required read models for home, approvals, issues, engagement list, engagement detail, and sent messages.
- Added matching API read-model endpoint contracts to `wiki/spec/api/engagement.md` under `/api/engagement/cockpit/*`.
- Kept legacy candidate, target, settings, and action endpoints as the mutation and low-level detail path while moving the main operator surfaces to explicit read models.

## [2026-04-27] docs | Add issue-fix mutation contract

- Added a semantic issue-action mutation layer to the task-first cockpit spec and API contract.
- Defined `POST /api/engagement/cockpit/issues/{issue_id}/actions/{action_key}` with `resolved`, `next_step`, `noop`, `stale`, and `blocked` results.
- Mapped each confirmed issue action either to a direct backend mutation or to a guided next-step flow such as the wizard or quiet-hours editor.
- Added recommended semantic helper mutations for target approval, resume sending, and permission sync so the bot does not construct raw low-level permission/status patches.

## [2026-04-27] docs | Define engagement-detail pending task contract

- Defined `pending_task` on engagement detail as a strict computed object instead of a loose hint.
- Added pending-task priority rules: `approvals` first, then `approval_updates`, then `issues`.
- Added scoped queue callbacks such as `eng:appr:eng:<engagement_id>` and `eng:iss:eng:<engagement_id>` so detail can resume work for one engagement and return back to that detail screen on completion.
- Aligned the API detail DTO so it returns `task_kind`, stable labels, scoped counts, and a scoped `resume_callback`.

## [2026-04-27] docs | Add display contract for secondary task-first screens

- Added explicit row/card display rules to `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`.
- Defined exact body shapes, badge placement, truncation rules, and empty-state copy for `Approve draft`, `Top issues`, `My engagements`, `Engagement detail`, and `Sent messages`.
- Kept the secondary-screen copy short and operator-readable while preventing backend diagnostics from leaking into the default card layouts.

## [2026-04-27] docs | Define task-first issue-generation rules

- Added an explicit issue-generation contract to the task-first cockpit spec.
- Defined how each confirmed issue type is derived from engagement, target, candidate, account, and settings state.
- Added de-duplication, removal, and recurrence rules so issues behave as stable read-model items instead of ad hoc UI guesses.
- Mirrored the same derivation rules into the cockpit issues API contract.

## [2026-04-27] docs | Make engagement a first-class backend entity

- Defined `engagement` as a first-class backend entity instead of treating the cockpit as community-only state plus global topics.
- Updated the wizard spec so setup creates or reuses an engagement record and writes topic/account/mode choices against that engagement.
- Added `engagements`, `engagement_settings`, and `engagement_topic_selections` to the storage docs.
- Added engagement-scoped write-path direction to the API spec and marked older community-scoped settings routes as legacy compatibility.
- Updated core lifecycle and settings docs so `auto_limited` is part of the active mode model rather than a permanently rejected future placeholder.

## [2026-04-27] docs | Define issue-fix subflow screens

- Defined which issue actions mutate immediately versus which enter a subflow.
- Added read-only `Rate limit active` detail-screen rules and editable `Change quiet hours` screen rules.
- Routed topic/account-related issue fixes through the existing engagement wizard with explicit return-context behavior.
- Kept direct fixes such as `Retry`, `Resume sending`, `Approve target`, `Resolve target`, and `Fix permissions` as no-intermediate-screen actions.

## [2026-04-27] docs | Define confirmation and result copy

- Added a dedicated confirmation/result-copy section to the task-first cockpit spec.
- Defined which actions require confirmation and kept direct issue fixes confirmation-free in the first version.
- Added short operator-facing success and error lines for draft actions, direct issue fixes, quiet-hours updates, and wizard confirm/cancel.
- Kept the copy terse, one-line, and free of backend error-code leakage.

## [2026-04-27] docs | Define wizard step layouts

- Added explicit step-screen layout rules to the task-first cockpit spec and the engagement wizard spec.
- Defined titles, step counters, prompt lines, button rows, and selection behavior for target, topic, account, sending-mode, and final-review screens.

## [2026-04-27] docs | Define edge and empty states for task-first surfaces

- Added a dedicated edge/empty-state section to the task-first cockpit spec.
- Defined what happens when scoped approval or issue queues launched from engagement detail run dry.
- Defined stale-item refresh behavior, issue-subflow return rules, and blocked account/topic picker behavior.
- Defined how list paging should recover when offsets become invalid after underlying data changes.

## [2026-04-27] docs | Define engagement-cockpit migration contract

- Added an explicit migration contract to the engagement API spec.
- Defined the compatibility boundary between legacy community-scoped settings routes and the new engagement-scoped cockpit read/write surface.
- Added cutover sequencing, idempotent backfill rules, and operator-facing fail-closed behavior for incomplete migration state.
- Mirrored the rollout order into the cockpit simplification rollout shard so implementation can retire old primary paths cleanly.

## [2026-04-27] docs | Collapse engagement topic model to one topic per engagement

- Replaced the older multi-topic engagement wording with a single chosen-topic contract.
- Added wizard write-contract language so step 2 writes one `topic_id` and final confirmation validates the full engagement draft.
- Updated storage docs to put `topic_id` on `engagements` and removed the separate `engagement_topic_selections` direction.
- Aligned cockpit issue-generation and API wording so `Topics not chosen` means no chosen topic on the engagement.

## [2026-04-27] docs | Make wizard API contract explicitly hybrid

- Clarified that wizard step fields use generic engagement write endpoints while workflow edges stay semantic.
- Marked `wizard-confirm` as the only wizard commit route and `wizard-retry` as the semantic reset route.
- Marked `POST /api/engagements/{engagement_id}/activate` as a legacy low-level compatibility route rather than the task-first wizard path.

## [2026-04-27] docs | Define wizard confirm and retry DTOs

- Added concrete response DTOs for `wizard-confirm` and `wizard-retry`.
- Defined result enums for success, validation failure, blocked, stale, and reset outcomes.
- Added `field`, `code`, `message`, and `next_callback` guidance so bot handlers can route without inventing ad hoc branches.

## [2026-04-27] docs | Define generic wizard step-write DTOs

- Added explicit request and response DTOs for `PATCH /api/engagements/{engagement_id}` and `PUT /api/engagements/{engagement_id}/settings`.
- Locked the engagement patch contract to one `topic_id` instead of any multi-topic payload shape.
- Added blocked/stale result handling for generic step writes so bot handlers can treat staged writes consistently with semantic wizard endpoints.

## [2026-04-27] docs | Define task-first bot handler contract

- Added an explicit callback-to-endpoint handler matrix to the task-first cockpit spec.
- Defined how approval, issue, list/detail, and wizard callbacks map onto read-model and mutation endpoints.
- Added result-handling rules so bot handlers know when to refresh, reroute by `next_callback`, or stay on the same card with short copy.

## [2026-04-27] docs | Define draft-approval mutation contract

- Added semantic task-first draft approval endpoints for approve, reject, and edit-request flows.
- Defined DTOs and result enums for `approved`, `rejected`, `queued_update`, `blocked`, and `stale` outcomes.
- Updated the bot-handler contract so approval callbacks point at the new cockpit draft-action routes instead of unnamed review mutations.

## [2026-04-27] docs | Define quiet-hours and rate-limit DTOs

- Added read DTOs for the task-first `Rate limit active` and `Change quiet hours` screens.
- Added a dedicated quiet-hours write endpoint with `updated`, `noop`, `blocked`, and `stale` outcomes.
- Kept quiet-hours mutation separate from generic settings writes so the issue-fix flow has its own stable contract.

## [2026-04-28] docs | Finish task-first spec polish

- Added explicit scoped approvals/issues read endpoints to the cockpit API contract.
- Folded rate-limit and quiet-hours subflow routing into the bot-handler matrix.
- Added a short terminology rule so operator-facing copy prefers `reply opportunity` and `draft` while legacy backend `candidate` names remain implementation-only.

## [2026-04-28] docs | Write task-first cockpit implementation plan

- Added a phased implementation plan for the task-first engagement cockpit.
- Sequenced delivery from schema/backfill through wizard writes, read models, semantic mutations, bot routing, queue flows, and legacy retirement.
- Added slice order, risk watchpoints, and definition-of-done guidance for build execution.

## [2026-04-28] docs | Break task-first cockpit plan into slices

- Added a dedicated slice plan for the task-first engagement cockpit.
- Broke delivery into mergeable slices covering schema, wizard writes, read models, semantic mutations, bot shell, wizard UI, queue controllers, detail/feed, and legacy retirement.
- Linked the high-level implementation plan to the new slices doc.
- Kept the topic branch equal-weight between choosing an existing topic and creating a new one.
- Kept the account chooser as a plain list and the final review screen read-only.

## [2026-04-27] docs | Define pagination and list controls

- Added a dedicated pagination/list-controls section to the task-first cockpit spec.
- Standardized `My engagements` and `Sent messages` on newest-first paging with `Newer` and `Older` controls.
- Kept queue controllers out of generic list pagination in the first version.
- Added the default page-size rule to the matching cockpit list endpoints in the API spec.

## [2026-04-28] code | Add task-first engagement schema foundation

- Added first-class `engagements` and `engagement_settings` SQLAlchemy models plus the new engagement lifecycle enum.
- Added a migration that creates the new tables and backfills legacy target/settings state into one engagement per resolved target without duplicating rows.
- Extended schema tests to cover the new defaults, indexes, unique constraints, and PostgreSQL DDL compilation.

## [2026-04-28] docs | Shard task-first cockpit plans

- Split the task-first cockpit implementation plan into phase shards to satisfy the wiki plan size cap.
- Split the detailed slice plan into two shard files while keeping the top-level plan entrypoints stable.
- Added the new shard directory to the wiki index so the fragmented plan layout stays discoverable.

## [2026-04-28] docs | Add task-first cockpit next-work queue

- Updated `wiki/plan/engagement-task-first-cockpit-slices.md` from a static slice index into a real next-work queue.
- Marked Slice 1 as complete and noted that the task-first wizard-write surface is already underway in code.
- Recommended execution order from Slice 3 onward, including the late home-shell cutover so old and new primary operator paths do not overlap.

## [2026-04-28] code | Fix fragmentation blockers for task-first cockpit push

- Split search API DTOs out of `backend/api/schemas.py` into `backend/api/schemas_search.py` while keeping the public import surface stable through the aggregator module.
- Split candidate/action engagement API coverage into `tests/test_engagement_api_candidates.py` so the main engagement API test shard stays under the test-file ceiling.
- Passed `python3 scripts/check_fragmentation.py`, `./.venv/bin/ruff check .`, and `./.venv/bin/pytest -q` after the split.

## [2026-04-28] fix | Repair task-first engagement migration backfill

- Replaced the `min(uuid)` aggregate in `20260428_0013_task_first_engagements` with a text-cast aggregate so Postgres can backfill single-topic engagements during deploy.
- Added a regression test that compiles the migration query against the PostgreSQL dialect and asserts the UUID aggregate does not return.

## [2026-04-28] fix | Cut engagement home callbacks over to the task-first cockpit

- Routed legacy `eng:home` callback traffic to the same task-first cockpit home used by `/engagement` so callback navigation no longer falls back to the older engagement home.
- Added bot-handler regression coverage proving `eng:home` renders the task-first `Engagements` home instead of rebuilding legacy candidate counts.
- Updated the Slice 7 plan shard to reflect that the task-first home and `op:*` callback family are already wired, with `eng:home` kept only as a compatibility alias for remaining legacy navigation buttons.

## [2026-04-28] fix | Serialize staging deploys per VPS checkout

- Added a checkout-local deploy lock to `scripts/vps-deploy.sh` so GitHub Actions deploys and manual `tg-outreach-deploy` runs cannot overlap on the same staging checkout.
- Exposed lock wait behavior through `TG_OUTREACH_DEPLOY_LOCK_WAIT_SECONDS` and included lock-holder metadata in timeout diagnostics.
- Updated the deployment spec, VPS pipeline plan, and redacted agent context to document the new hardening behavior.
## [2026-04-28] fix | Allow duplicate engagement targets per community

- Removed the engagement-target uniqueness rule on `community_id` so operators can add the same
  Telegram group to multiple engagement target rows.
- Stopped engagement target creation from reusing an older row with the same submitted ref, while
  keeping public refs normalized for consistent audit history.
- Tightened worker permission checks so join, detect, and send actions succeed when any approved
  target row for the community grants the requested permission.

## [2026-04-28] fix | Remove duplicated /api prefix from engagement wizard client routes

- Investigated the staging task-first engagement wizard failure that surfaced as `Couldn't create engagement: Not Found`.
- Confirmed from staging API logs that Step 1 succeeded with `POST /api/engagement/targets` and the follow-up draft creation failed on `POST /api/api/engagements`.
- Fixed the wizard-only `BotApiClient` engagement create/update/confirm/retry methods to call `/engagements...` so the configured `.../api` base URL resolves to the documented task-first routes.
- Aligned Step 1 with the wizard spec by waiting for target resolution when link intake returns `pending`, then creating the draft engagement only after the target reaches a usable resolved state.
- Added regression coverage for both the wizard request sequence and the pending-target resolution path.

## [2026-04-28] docs | Add completed-branch merge rule for agents

- Added `wiki/plan/agent-merge-to-main.md` to record the repo workflow decision that completed
  agent branches should land in `main`.
- Updated `AGENTS.md` and `CLAUDE.md` so branch-scoped work that passes local parity is merged
  into `main` unless the operator explicitly keeps the branch open.
- Aligned the deployment spec and wiki index with the same durable-branch workflow rule.

## [2026-04-28] fix | Keep add-engagement wizard responsive after community intake

- Traced the live "no response after sending @handle or t.me link" failure to Step 2 callback
  construction: topic/account picker buttons included two full UUIDs and could exceed Telegram's
  64-byte callback limit before the bot sent the next wizard message.
- Added compact UUID callback encoding plus matching decode logic for the wizard's topic and
  account pick callbacks, while tolerating legacy non-UUID fixture IDs so older tests and helper
  clients still work.
- Strengthened wizard regression coverage with production-sized UUID IDs and an assertion that the
  Step 2 callback payloads stay within Telegram's limit.

## [2026-04-28] fix | Auto-join community on wizard confirm instead of blocking

- Removed the hard block when the engagement account isn't joined at wizard confirm time.
- Wizard confirm now enqueues `community.join` automatically when membership is missing or not
  in `JOINED` state, then continues to create the engagement so the operator sees immediate
  confirmation rather than an error.
- Bypassed the `allow_join` / `mode` settings gate inside the community join worker when the
  payload carries an explicit `telegram_account_id` (wizard-triggered joins), while preserving
  the gate for scheduler-driven joins with no explicit account.
- Added regression coverage in `tests/test_engagement_api.py` for both paths.

## [2026-04-28] fix | Finish wizard confirm regressions and restore CI fragmentation parity

- Fixed the new wizard-confirm join regression stub so it matches the production
  `enqueue_community_join` keyword call shape instead of silently tripping the
  service's enqueue-failure fallback.
- Split the task-first wizard confirm tests into
  `tests/test_engagement_task_first_wizard_api.py` so the oversized
  `tests/test_engagement_api.py` file drops back under the fragmentation guardrail.
- Verified `python scripts/check_fragmentation.py`, `ruff check .`, and targeted
  task-first engagement tests pass after the split.

## [2026-04-28] fix | Shorten topic edit callbacks for UUID topic IDs

- Confirmed the topic detail buttons for guidance, trigger keywords, and negative keywords could
  exceed Telegram's 64-byte callback limit when `engagement_topics.id` is a UUID because the
  callback payload embedded the full field name.
- Switched topic edit buttons to short field codes (`s`, `t`, `n`) while keeping the callback
  handler backward-compatible with older long-form payloads that may still be present in sent
  messages.
- Added UI and handler regression coverage proving UUID topic callbacks stay under Telegram's
  limit and that both the new short-form and older long-form edit callbacks still route correctly.

## [2026-04-28] fix | Start wizard joins at Step 3 and show connecting state

- Stored `community_id` in task-first wizard state so Step 3 can queue
  `community.join` as soon as the operator chooses an engagement account.
- Updated the bot wizard to carry a clear join-status note into later steps,
  including `connecting` while the join is still in flight and `joined` when a
  fast completion is already visible.
- Kept the wizard on Step 3 when the join fails immediately so the operator can
  retry or pick another account instead of walking into a misleading confirm
  screen.
- Added a distinct `Account connecting` issue label/tip when the assigned
  membership is already in `join_requested`.
- Added Step 3 regressions for queued, joined, and failed join flows.
