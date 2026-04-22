# API Engagement

Engagement target, settings, topic, prompt, style, candidate, action, and rollout endpoint contracts.

## Engagement

Engagement endpoints are optional/future. They must remain operator-controlled and separate from
discovery snapshots and analysis.

Admin-only engagement mutations are authorized by backend capabilities when
`ENGAGEMENT_ADMIN_USER_IDS` is configured. The bot sends `X-Telegram-User-Id`; protected target,
prompt-profile, style-rule, topic, and community engagement-settings mutation routes return
`403 engagement_admin_required` for non-admin operators. Read-only daily review routes and ordinary
candidate review/send routes remain available to allowed operators when the backend permits them.

### `GET /api/engagement/targets`

Lists manual engagement targets. Targets are the explicit engagement allowlist and are separate from
seed groups, direct handle intakes, and community review.

Query parameters:

- `status`
- `limit`
- `offset`

### `GET /api/engagement/targets/{target_id}`

Returns one manual engagement target with submitted reference, resolved community fields when
available, status, permissions, notes, approval metadata, and last error.

### `POST /api/engagement/targets`

Creates or returns an engagement target from an existing `community_id`, public Telegram username,
or public Telegram link.

Request:

```json
{
  "target_ref": "@example",
  "notes": "Manual engagement candidate",
  "added_by": "telegram_user_id_or_operator"
}
```

Rules:

- Existing `community_id` targets are created as `resolved`.
- Public username/link targets are created as `pending` and must be resolved by an engagement job.
- Duplicate normalized targets return the existing row instead of creating seed rows.
- Private invite-link resolution remains out of scope for MVP.

### `PATCH /api/engagement/targets/{target_id}`

Updates target status, notes, and engagement permissions.

Request:

```json
{
  "status": "approved",
  "allow_join": true,
  "allow_detect": true,
  "allow_post": false,
  "updated_by": "telegram_user_id_or_operator"
}
```

Rules:

- A target must resolve to a community before it can be approved.
- Rejected and archived targets force `allow_join`, `allow_detect`, and `allow_post` to false.
- Approving a target records `approved_by` and `approved_at`.

### `POST /api/engagement/targets/{target_id}/resolve-jobs`

Queues `engagement_target.resolve`. This is an engagement job, not a seed job.

Request:

```json
{
  "requested_by": "telegram_user_id_or_operator|null"
}
```

### `POST /api/engagement/targets/{target_id}/join-jobs`

Queues `community.join` for the target's resolved community. The worker still enforces target
approval and `allow_join`.

### `POST /api/engagement/targets/{target_id}/detect-jobs`

Queues manual `engagement.detect` for the target's resolved community. The worker still enforces
target approval and `allow_detect`.

### `GET /api/communities/{community_id}/engagement-settings`

Returns engagement settings for one community. If no settings exist, engagement is disabled.

### `PUT /api/communities/{community_id}/engagement-settings`

Creates or updates per-community engagement settings.

Request:

```json
{
  "mode": "suggest",
  "allow_join": true,
  "allow_post": false,
  "reply_only": true,
  "require_approval": true,
  "max_posts_per_day": 1,
  "min_minutes_between_posts": 240
}
```

MVP rules:

- `require_approval` must remain true.
- `reply_only` must remain true.
- Settings are disabled unless explicitly created or enabled.

### `POST /api/communities/{community_id}/join-jobs`

Queues `community.join` after verifying the community exists. The API does not call Telethon
directly.

Request:

```json
{
  "telegram_account_id": "uuid-or-null",
  "requested_by": "telegram_user_id_or_operator|null"
}
```

Response `202`:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "community.join",
    "status": "queued"
  }
}
```

### `GET /api/engagement/topics`

Lists configured engagement topics.

### `GET /api/engagement/topics/{topic_id}`

Returns one engagement topic with guidance, trigger keywords, negative keywords, and ordered good
and bad example arrays.

### `POST /api/engagement/topics`

Creates an engagement topic.

### `PATCH /api/engagement/topics/{topic_id}`

Updates an engagement topic.

### `POST /api/engagement/topics/{topic_id}/examples`

Adds a good or bad reply example to a topic. Good examples are positive guidance; bad examples are
negative examples only and must not be copied as reply templates.

### `DELETE /api/engagement/topics/{topic_id}/examples/{example_type}/{index}`

Removes a topic example by ordered array index. `example_type` is `good` or `bad`.

### `GET /api/engagement/prompt-profiles`

Lists admin-managed engagement prompt profiles with current immutable version metadata.

### `POST /api/engagement/prompt-profiles`

Creates a prompt profile and version 1. Fields include name, model, temperature,
max_output_tokens, system_prompt, user_prompt_template, output_schema_name, active, and created_by.

### `GET /api/engagement/prompt-profiles/{profile_id}`

Returns one prompt profile with current version metadata, model parameters, output schema, capped
bot-safe prompt preview fields, active state, and audit metadata.

### `PATCH /api/engagement/prompt-profiles/{profile_id}`

Updates editable prompt profile fields and creates a new immutable version row.

### `POST /api/engagement/prompt-profiles/{profile_id}/activate`

Activates one prompt profile and deactivates other active profiles.

### `POST /api/engagement/prompt-profiles/{profile_id}/duplicate`

Copies an existing prompt profile into a new inactive profile with a new name and version 1.

### `POST /api/engagement/prompt-profiles/{profile_id}/rollback`

Restores a selected immutable version into the current profile state and creates a new current
version representing that rollback.

### `POST /api/engagement/prompt-profiles/{profile_id}/preview`

Renders the prompt template with approved variables only. This endpoint does not call OpenAI.

### `GET /api/engagement/prompt-profiles/{profile_id}/versions`

Lists immutable prompt profile versions newest first.

### `GET /api/engagement/style-rules`

Lists style rules by optional scope, scope ID, active state, limit, and offset.

### `GET /api/engagement/style-rules/{rule_id}`

Returns one style rule with scope, scope ID, active state, priority, rule text, and update
metadata.

### `POST /api/engagement/style-rules`

Creates a global, account, community, or topic style rule.

### `PATCH /api/engagement/style-rules/{rule_id}`

Updates style rule text, priority, scope, or active state.

### `POST /api/communities/{community_id}/engagement-detect-jobs`

Queues `engagement.detect`.

### `GET /api/engagement/candidates`

Lists candidate replies for operator review.

Query parameters:

- `status` - default `needs_review`
- `community_id`
- `topic_id`
- `limit`
- `offset`

### `GET /api/engagement/candidates/{candidate_id}`

Returns one candidate reply detail for bot review. The response uses the same safe candidate fields
as the candidate list: community/topic labels, capped source excerpt, detected reason, suggested
reply, final reply, prompt provenance, risk notes, status, review metadata, expiry, and timestamps.
It must not expose sender identity, phone numbers, private account metadata, or person-level scores.

### `GET /api/engagement/candidates/{candidate_id}/revisions`

Returns immutable manual reply revision history newest first.

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "candidate_id": "uuid",
      "revision_number": 1,
      "reply_text": "edited final public reply",
      "edited_by": "telegram:123",
      "edit_reason": "manual edit",
      "created_at": "iso_datetime"
    }
  ],
  "total": 1
}
```

### `POST /api/engagement/candidates/{candidate_id}/approve`

Approves a candidate reply. The API records the reviewer and review timestamp. Sending still happens
through `engagement.send`.

If an edited `final_reply` already exists, approval uses that text. If no edit exists, approval
falls back to the generated `suggested_reply`.

### `POST /api/engagement/candidates/{candidate_id}/edit`

Stores an edited final reply, creates an immutable candidate revision row, and keeps the candidate in
review until explicitly approved.

### `POST /api/engagement/candidates/{candidate_id}/reject`

Rejects a candidate reply.

### `POST /api/engagement/candidates/{candidate_id}/expire`

Explicitly expires a reviewable candidate so it leaves the active review/send queue. Sent, rejected,
and already expired candidates are not expirable.

### `POST /api/engagement/candidates/{candidate_id}/retry`

Reopens a failed candidate for review when it has not expired. Other statuses are rejected.

### `POST /api/engagement/candidates/{candidate_id}/send-jobs`

Queues `engagement.send` for an approved candidate.

### `GET /api/engagement/actions`

Lists outbound action audit rows.

Query parameters:

- `community_id`
- `candidate_id`
- `status`
- `action_type`
- `limit`
- `offset`

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "candidate_id": "uuid-or-null",
      "community_id": "uuid",
      "telegram_account_id": "uuid",
      "action_type": "reply",
      "status": "sent",
      "outbound_text": "exact approved public reply",
      "reply_to_tg_message_id": 123,
      "sent_tg_message_id": 456,
      "scheduled_at": "iso_datetime|null",
      "sent_at": "iso_datetime|null",
      "error_message": null,
      "created_at": "iso_datetime"
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

Rules:

- API handlers must not call Telethon directly.
- API responses must not expose phone numbers.
- API responses must not expose person-level scores.
- Engagement workers fail closed unless an approved engagement target grants the matching
  join/detect/post permission.
- Audit rows should remain available for operator review.

### `GET /api/engagement/semantic-rollout`

Returns aggregate semantic-selector rollout outcomes for threshold tuning.

Query parameters:

- `window_days` - default `14`, range `1..90`
- `community_id` - optional community filter
- `topic_id` - optional topic filter

Response:

```json
{
  "window_days": 14,
  "community_id": null,
  "topic_id": null,
  "total_semantic_candidates": 3,
  "reviewed_semantic_candidates": 2,
  "pending": 1,
  "approved": 1,
  "rejected": 1,
  "expired": 0,
  "approval_rate": 0.5,
  "bands": [
    {
      "label": "0.80-0.89",
      "min_similarity": 0.8,
      "max_similarity": 0.9,
      "total": 1,
      "pending": 0,
      "approved": 1,
      "rejected": 0,
      "expired": 0,
      "approval_rate": 1.0,
      "average_similarity": 0.83
    }
  ]
}
```

Rules:

- The endpoint reads compact semantic metadata already stored on reply opportunities.
- Output is aggregate-only. It must not expose source excerpts, sender identity, candidate IDs,
  phone numbers, or person-level scores.
