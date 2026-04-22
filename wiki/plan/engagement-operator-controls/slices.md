# Engagement Operator Controls Slices

Detailed implementation slices for API, bot, settings, topics, audit, docs, and tests.

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

Status: completed.

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

Completed notes:

- `/engagement_settings <community_id>` now renders the API-provided settings view, including
  missing-row disabled synthetic settings, and shows preset, join, post, queue-join, and detect
  controls.
- `/set_engagement <community_id> <off|observe|suggest|ready>` applies safe presets that preserve
  `reply_only=true`, `require_approval=true`, `max_posts_per_day=1`, and
  `min_minutes_between_posts=240`.
- Community detail cards now include an `Engagement` button that opens the settings surface.
- `/join_community <community_id>` and `eng:join:<community_id>` queue `community.join` through the
  bot API client only.
- `/detect_engagement <community_id> [window_minutes]` and
  `eng:detect:<community_id>:<window_minutes>` queue manual `engagement.detect` through the bot API
  client only.
- Focused fake-client bot tests cover disabled synthetic display, presets, settings callbacks,
  explicit join/detect commands, and join/detect callbacks.
## Slice 5: Topic Management

Status: completed.

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

Completed notes:

- `/engagement_topics` now lists topic cards with active/inactive state, trigger keyword previews,
  truncated guidance, and inline activate/deactivate controls.
- `/create_engagement_topic <name> | <guidance> | <comma_keywords>` parses the planned pipe syntax,
  requires at least one trigger keyword before calling the API, and creates active topics through
  the bot API client only.
- `/toggle_engagement_topic <topic_id> <on|off>` and `eng:topic:toggle:<topic_id>:<0|1>` patch the
  topic active state through the API client and return refreshed topic cards.
- Parser failures return usage copy with an example instead of calling the API.
## Slice 6: Audit Surface

Status: completed.

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

Completed notes:

- `/engagement_actions [community_id]` lists recent audit actions, optionally filtered by
  community, using the bot API client only.
- Action cards show action type, status, community ID, candidate ID, reply target message ID, sent
  Telegram message ID, capped outbound text, error message, and created/sent timestamps when
  present.
- Inline audit paging uses `eng:actions:list:<offset>` for global views and preserves community
  filters with `eng:actions:list:<community_id>:<offset>`.
- Completed audit rows are read-only in this bot slice.
- Focused fake-client bot tests cover community filtering and paged callback views.
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
