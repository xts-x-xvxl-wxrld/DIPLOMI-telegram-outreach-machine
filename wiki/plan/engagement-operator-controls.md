# Engagement Operator Controls Plan

## Goal

Extend the Telegram operator bot into a practical control surface for the engagement module described
in `wiki/spec/engagement.md`.

The operator should be able to:

- see engagement status from one place
- manage engagement topics
- view and update per-community engagement settings
- queue joins and manual detection runs
- review, approve, reject, and explicitly queue approved replies for sending
- inspect outbound action audit rows

The surface remains conservative: no automatic sending, no direct messages, no person-level scores,
and no bot code that talks directly to Telethon, Redis, Postgres, OpenAI, or workers.

## Current Context

Already implemented:

- Engagement schema, service layer, workers, scheduler, and most API routes exist.
- Bot has basic candidate review:
  - `/engagement_candidates`
  - `/approve_reply <candidate_id>`
  - `/reject_reply <candidate_id>`
  - inline approve/reject candidate buttons
- Bot API client can list candidates and approve/reject them.

Known backend/API gaps before a full bot surface:

- `POST /api/communities/{community_id}/join-jobs` is specified but not implemented in
  `backend/api/routes/engagement.py`.
- `GET /api/engagement/actions` is specified but not implemented.
- API schemas do not yet expose `EngagementActionOut`.
- Candidate list route currently supports status, limit, and offset only. The engagement spec also
  calls for `community_id` and `topic_id` filters.

## UX Principles

- Keep the first screen operational, not explanatory.
- Prefer buttons for safe bounded choices and commands only for ID-targeted operations.
- Separate approval from sending. Approval records human review; sending queues a distinct
  `engagement.send` job.
- Any control that can create outbound Telegram behavior must be explicit and auditable.
- Settings edits should use safe presets and toggles first. Free-form editing can come later.
- All cards must keep source excerpts short and must never expose sender identity or phone numbers.

## Target Bot Commands

Core engagement commands:

```text
/engagement
/engagement_topics
/engagement_settings <community_id>
/set_engagement <community_id> <off|observe|suggest|ready>
/join_community <community_id>
/detect_engagement <community_id> [window_minutes]
/engagement_candidates [status]
/approve_reply <candidate_id>
/reject_reply <candidate_id>
/send_reply <candidate_id>
/engagement_actions [community_id]
```

Topic editing command syntax for the first bot slice:

```text
/create_engagement_topic <name> | <guidance> | <comma_keywords>
/toggle_engagement_topic <topic_id> <on|off>
```

The pipe syntax is intentionally plain. Rich multi-field topic editing can wait for a web frontend
or a later conversation-state bot flow.

## Target Inline Controls

Engagement home:

```text
eng:home
eng:topic:list:<offset>
eng:cand:list:<status>:<offset>
eng:actions:list:<offset>
```

Community settings and jobs:

```text
eng:set:open:<community_id>
eng:set:preset:<community_id>:<off|observe|suggest|ready>
eng:set:join:<community_id>:<0|1>
eng:set:post:<community_id>:<0|1>
eng:join:<community_id>
eng:detect:<community_id>:<window_minutes>
```

Candidates:

```text
eng:cand:approve:<candidate_id>
eng:cand:reject:<candidate_id>
eng:cand:send:<candidate_id>
eng:cand:open:<candidate_id>
```

Topics:

```text
eng:topic:open:<topic_id>
eng:topic:toggle:<topic_id>:<0|1>
```

Callback data must stay under Telegram's 64-byte limit. UUID-bearing callbacks should keep action
segments short, and `bot.ui.parse_callback_data` should handle all `eng:*` namespaces instead of
only `eng:cand:*`.

## Setting Presets

The bot should use presets instead of asking operators to remember every settings field.

| Preset | API payload intent |
|---|---|
| `off` | `mode=disabled`, `allow_join=false`, `allow_post=false` |
| `observe` | `mode=observe`, `allow_join=false`, `allow_post=false` |
| `suggest` | `mode=suggest`, `allow_join=false`, `allow_post=false` |
| `ready` | `mode=require_approval`, `allow_join=true`, `allow_post=true` |

All presets preserve MVP safety fields:

```text
reply_only = true
require_approval = true
max_posts_per_day = 1
min_minutes_between_posts = 240
```

The bot may display quiet hours and assigned account IDs if present, but editing those fields is a
later slice unless the operator asks for it.

## Slice 1: API Gap Closure

Status: completed.

Add backend endpoints needed by the bot:

```http
POST /api/communities/{community_id}/join-jobs
GET  /api/engagement/actions
```

Also add:

- `EngagementActionOut`
- `EngagementActionListResponse`
- optional `community_id`, `candidate_id`, `status`, `action_type`, `limit`, and `offset` filters
  for action listing
- `community_id` and `topic_id` filters for candidate listing

Acceptance:

- Join endpoint verifies the community exists and enqueues `community.join`; it does not call
  Telethon.
- Action listing returns audit rows without phone numbers or person-level data.
- API tests cover auth, missing rows, queue failure, filters, and response shape.

## Slice 2: Bot Client And Formatting Foundation

Status: completed.

Extend `bot/api_client.py` with methods for:

- engagement settings get/update
- topic list/create/update
- join job enqueue
- manual detection enqueue
- send job enqueue
- action audit listing
- filtered candidate listing

Extend `bot/formatting.py` with compact formatters for:

- engagement home summary
- settings card
- topic list and topic card
- join, detect, and send job responses
- action audit list
- candidate review result with next-step send controls

Extend `bot/ui.py` with:

- engagement main menu button
- engagement home keyboard
- settings preset/toggle markup
- topic pager/toggle markup
- candidate status filter and send markup
- action pager markup

Acceptance:

- All bot HTTP methods have tests using `httpx.MockTransport`.
- Formatting tests verify truncation order and no raw sender/person fields.
- Callback parser tests cover every new `eng:*` namespace and 64-byte safety.

## Slice 3: Engagement Home And Candidate Send Flow

Status: completed.

Add `/engagement` as the operator cockpit.

Home should show:

- pending reply count
- approved-but-not-sent count
- failed candidate count
- active topic count
- quick commands for topics, candidates, and actions

Upgrade candidate review:

- `/engagement_candidates [status]` supports `needs_review`, `approved`, `failed`, `sent`, and
  `rejected`.
- Approved candidate cards expose `Queue send`.
- `/send_reply <candidate_id>` calls the send-job API.
- After `/approve_reply`, the bot shows a `Queue send` button but does not send automatically.

Acceptance:

- Operator can approve a candidate, then explicitly queue send from the returned card.
- Unapproved candidates do not expose a send button.
- Send job response includes job ID and refresh button.
- Tests cover command handlers and inline callbacks with a fake bot API client.

Completed notes:

- `/engagement` now builds the cockpit from candidate status totals and active topic count.
- `/engagement_candidates [status]` supports `needs_review`, `approved`, `failed`, `sent`, and
  `rejected` views.
- Approved candidates expose `Queue send`; pending and failed candidates expose review controls.
- `/send_reply <candidate_id>` and `eng:cand:send:<candidate_id>` queue `engagement.send` through
  the bot API client only.
- Approval returns a send button without enqueueing send automatically.

## Slice 4: Community Settings And Manual Jobs

Status: planned.

Add community-level controls:

- `/engagement_settings <community_id>` shows current settings and safe presets.
- `/set_engagement <community_id> <off|observe|suggest|ready>` applies a preset.
- Community detail cards include an `Engagement` button.
- Settings cards include buttons for `Off`, `Observe`, `Suggest`, and `Ready`.
- Settings cards include `Queue join` and `Detect now` buttons when the current settings make those
  actions meaningful.
- `/join_community <community_id>` queues `community.join`.
- `/detect_engagement <community_id> [window_minutes]` queues manual `engagement.detect`.

Acceptance:

- Missing settings render as disabled synthetic settings without creating a row.
- Presets preserve required MVP safety fields.
- Join and detect commands return job cards with refresh buttons.
- Bot tests prove the bot talks only to API client methods.

## Slice 5: Topic Management

Status: planned.

Add topic controls:

- `/engagement_topics` lists topics with active/inactive state and keyword preview.
- `/create_engagement_topic <name> | <guidance> | <comma_keywords>` creates a conservative topic.
- `/toggle_engagement_topic <topic_id> <on|off>` changes `active`.
- Topic cards include activate/deactivate buttons.

Acceptance:

- Active topic creation requires at least one trigger keyword, matching service validation.
- Topic guidance is truncated in bot cards but not silently changed.
- Disallowed guidance remains enforced by the backend service.
- Tests cover parser failures with helpful usage messages.

## Slice 6: Audit Surface

Status: planned.

Add `/engagement_actions [community_id]` and inline audit paging.

Action cards should show:

- action type
- status
- community
- candidate ID when present
- reply target message ID when present
- sent Telegram message ID when present
- short error message for failed/skipped actions
- created/sent timestamps

Acceptance:

- Audit view can filter by community.
- Outbound text is shown only in capped form.
- Failed and skipped sends are visible enough for operator diagnosis.
- The bot never offers edits to completed audit rows in this slice.

## Slice 7: Documentation, Tests, And Release Commit

Status: planned.

Update after implementation:

- `wiki/spec/bot.md` with final command behavior
- `wiki/spec/api.md` if API route behavior changes
- `wiki/log.md` with completed slice notes

Run:

```text
npm.cmd test -- --run
```

and any focused Python tests used by the repo workflow.

Acceptance:

- Bot, API, and service tests pass.
- Wiki index links any new plan/spec files.
- Changes are committed and pushed when a remote is configured.

## Open Questions

- Should `ready` use `mode=suggest` with `allow_post=true`, or `mode=require_approval` with
  `allow_post=true`? The current plan chooses `require_approval` because it reads safest to an
  operator.
- Should topic creation remain command-only, or should a later conversation-state wizard collect
  name, guidance, and keywords step by step?
- Should the bot expose assigned account selection, or should account assignment remain backend/API
  only until we have stronger account-health UX?
- Should approved candidates expire from the bot's send queue visually before the API rejects them?

## Non-Goals

- No automatic posting.
- No editing final replies in the first controls slice.
- No direct messages.
- No top-level posts.
- No raw message browsing.
- No person-level scoring, ranking, or outreach priority views.
