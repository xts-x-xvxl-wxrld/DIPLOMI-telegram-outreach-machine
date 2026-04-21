# Brief Discovery Slice Plan

Status: superseded for the active MVP by `wiki/plan/seed-first-discovery.md`.

This plan is retained as historical and optional/future context. The current product direction is
seed-first discovery from example Telegram communities, not brief-first discovery from natural
language.

## Goal

Original goal:

```text
operator enters audience text
  -> API stores raw audience brief
  -> brief.process creates structured search fields
  -> discovery.run uses configured discovery sources
  -> candidates are stored for operator review
  -> bot lists candidates and supports approve/reject
```

## Locked Decisions

1. Audience brief extraction is asynchronous.
2. `POST /api/briefs` enqueues `brief.process`, not `discovery.run` directly.
3. OpenAI calls are allowed only in `brief.process` and `analysis.run`.
4. Discovery uses manual seeds, public web-search adapters, Telegram-native search adapters, and graph expansion instead of TGStat.
5. Discovery ranking and `match_reason` generation are deterministic and explainable.
6. Discovery does not auto-expand by default.
7. Telegram bot is the MVP operator UI before a web frontend.
8. Raw message storage remains opt-in per community.
9. MVP approve behavior moves a community directly to `monitoring` and queues an initial snapshot.

## Work Items

### Specs

- Create `wiki/spec/audience-brief.md`.
- Create `wiki/spec/discovery.md`.
- Create `wiki/spec/bot.md`.
- Update architecture, queue, and API specs for `brief.process`.
- Update wiki index and log.

### Backend Contracts

- Add a `brief.process` queue payload.
- Add enqueue helper for `brief.process`.
- Change `POST /api/briefs` to enqueue `brief.process`.
- Preserve `auto_start_discovery` as a flag passed into `brief.process`.
- Update job schemas/tests to expect `brief.process`.

### Brief Worker

- Add a brief-processing worker module.
- Read `audience_briefs.raw_input`.
- Call OpenAI with a structured JSON response contract.
- Validate caps and field types.
- Write structured arrays to `audience_briefs`.
- Enqueue `discovery.run` only after successful validation when `auto_start_discovery = true`.

### Discovery Worker

- Add a discovery source adapter contract.
- Implement public Telegram link normalization for source results.
- Keep manual seed import as the MVP discovery input.
- Normalize source results into resolvable seed candidates.
- Deduplicate by normalized username, canonical Telegram URL, then resolved `tg_id`.
- Preserve operator-controlled statuses and `store_messages`.
- Generate deterministic scores and `match_reason`.

### Bot MVP

- Implement `/start`.
- Implement `/brief <text>`.
- Implement `/candidates <brief_id>`.
- Implement `/approve <community_id>`.
- Implement `/reject <community_id>`.
- Implement `/job <job_id>`.
- Implement `/accounts` once the debug endpoint is wired.

## Non-Goals

- No Telethon expansion in this slice.
- No collection implementation beyond already-scaffolded enqueue behavior.
- No community analysis implementation.
- No web frontend.
- No direct outreach automation.
- No person-level scores.

## Acceptance Criteria

- Creating a brief queues `brief.process`.
- Successful brief processing fills structured fields.
- Successful brief processing can enqueue discovery.
- Discovery inserts candidate communities from resolved public Telegram seeds.
- Duplicate discovery results do not reset rejected or monitored communities.
- Bot can submit a brief and list/review candidates through the API.
- Tests cover queue payloads, brief processing validation, discovery normalization, and candidate dedupe behavior.
