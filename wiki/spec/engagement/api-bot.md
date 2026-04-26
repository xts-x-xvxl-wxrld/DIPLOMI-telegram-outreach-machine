# Engagement API And Bot Surface

API DTO and Telegram bot surface details for engagement operator workflows.

## API Surface

The implemented API and bot flow are centered on reply opportunities derived from runtime prompt
rendering. They are not centered on pre-authored outbound engagement messages.

Initial endpoints:

```http
GET  /api/communities/{community_id}/engagement-settings
PUT  /api/communities/{community_id}/engagement-settings
POST /api/communities/{community_id}/join-jobs
POST /api/engagement/targets/{target_id}/collection-jobs
GET  /api/engagement/targets/{target_id}/collection-runs
GET  /api/engagement/topics
POST /api/engagement/topics
PATCH /api/engagement/topics/{topic_id}
POST /api/communities/{community_id}/engagement-detect-jobs
GET  /api/engagement/candidates
POST /api/engagement/candidates/{candidate_id}/approve
POST /api/engagement/candidates/{candidate_id}/reject
POST /api/engagement/candidates/{candidate_id}/send-jobs
GET  /api/engagement/actions
```

API rules:

- Bot and API auth remain required.
- Engagement settings default to disabled unless explicitly created.
- Reply opportunity approval records the approving operator.
- Approval may accept the runtime-generated `suggested_reply` as-is or persist an operator-edited
  `final_reply` before send.
- The send endpoint enqueues a job; it should not call Telethon directly.
- Target-scoped manual collection requires an approved engagement target with `allow_detect = true`
  and enqueues `collection.run`; collection-run listing exposes recent status and message counts for
  operator verification.
- API responses must not expose phone numbers or person-level scores.

### Request And Response DTOs

`EngagementSettingsOut`:

```json
{
  "community_id": "uuid",
  "mode": "disabled",
  "allow_join": false,
  "allow_post": false,
  "reply_only": true,
  "require_approval": true,
  "max_posts_per_day": 1,
  "min_minutes_between_posts": 240,
  "quiet_hours_start": null,
  "quiet_hours_end": null,
  "assigned_account_id": null,
  "created_at": "iso_datetime|null",
  "updated_at": "iso_datetime|null"
}
```

`EngagementTopicOut`:

```json
{
  "id": "uuid",
  "name": "Open-source CRM",
  "description": "string|null",
  "stance_guidance": "string",
  "trigger_keywords": ["crm"],
  "negative_keywords": [],
  "example_good_replies": [],
  "example_bad_replies": [],
  "active": true,
  "created_at": "iso_datetime",
  "updated_at": "iso_datetime"
}
```

`EngagementReplyOpportunityOut`:

The current API may still expose this as `EngagementCandidateOut` until the code-level rename is
complete.

```json
{
  "id": "uuid",
  "community_id": "uuid",
  "community_title": "string|null",
  "topic_id": "uuid",
  "topic_name": "string",
  "source_tg_message_id": 123,
  "source_excerpt": "truncated text",
  "source_message_date": "iso_datetime",
  "detected_reason": "plain-language reason",
  "moment_strength": "good",
  "timeliness": "fresh",
  "reply_value": "practical_tip",
  "suggested_reply": "draft reply",
  "final_reply": null,
  "risk_notes": [],
  "status": "needs_review",
  "reviewed_by": null,
  "reviewed_at": null,
  "review_deadline_at": "iso_datetime|null",
  "reply_deadline_at": "iso_datetime",
  "operator_notified_at": "iso_datetime|null",
  "expires_at": "iso_datetime",
  "created_at": "iso_datetime"
}
```

`EngagementActionOut`:

```json
{
  "id": "uuid",
  "candidate_id": "uuid|null",
  "community_id": "uuid",
  "telegram_account_id": "uuid",
  "action_type": "reply",
  "status": "sent",
  "outbound_text": "exact text",
  "reply_to_tg_message_id": 123,
  "sent_tg_message_id": 456,
  "scheduled_at": "iso_datetime|null",
  "sent_at": "iso_datetime|null",
  "error_message": null,
  "created_at": "iso_datetime"
}
```

## Bot Surface

The Telegram bot may expose operator controls:

```text
/engagement_topics
/engagement_opportunities
/engagement_candidates
/approve_reply <candidate_id>
/reject_reply <candidate_id>
/join_community <community_id>
/target_collect <target_id>
/target_collection_runs <target_id>
```

`/engagement_candidates` and `eng:cand:*` are legacy command/callback names. Bot copy should say
reply opportunity. The bot should treat `candidate` as implementation vocabulary and `reply
opportunity` as operator vocabulary.

Inline review cards should show:

- community title
- matched topic
- capped source excerpt
- suggested reply
- current `final_reply` when it differs from the suggestion
- approval / review state and deadlines
- approve/send button
- reject button

Editing is part of the current workflow contract: operators may edit the generated suggestion into a
durable `final_reply` before approval or send.

Bot callback contract:

```text
eng:cand:list:<page>
eng:cand:approve:<candidate_id>
eng:cand:reject:<candidate_id>
eng:cand:send:<candidate_id>
eng:topic:list:<page>
eng:join:<community_id>
```

Bot messages must keep source excerpts and suggested replies short enough for Telegram message
limits. If a reply opportunity card would exceed Telegram limits, the bot should truncate the
excerpt first, then the detected reason, never the final reply text.
