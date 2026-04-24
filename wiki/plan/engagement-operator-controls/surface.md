# Engagement Operator Controls Surface

Goal, context, UX principles, commands, inline controls, presets, open questions, and non-goals.

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
/create_engagement_topic
/toggle_engagement_topic <topic_id> <on|off>
```

The bot now prefers a conversation-state flow for topic creation. Legacy pipe syntax may still be
accepted when operators supply inline arguments directly.
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
