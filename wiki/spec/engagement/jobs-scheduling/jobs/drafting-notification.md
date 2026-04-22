# Engagement Drafting And Notification

Detailed draft model input and operator notification contracts.

### Draft Model Input Contract

Draft-generation input should be lean and centered on one selected trigger post.

```json
{
  "community": {
    "id": "uuid",
    "title": "string|null",
    "username": "string|null",
    "description": "string|null",
    "is_group": true
  },
  "topic": {
    "id": "uuid",
    "name": "string",
    "description": "string|null",
    "stance_guidance": "string",
    "trigger_keywords": ["string"],
    "negative_keywords": ["string"],
    "example_good_replies": ["string"],
    "example_bad_replies": ["string"]
  },
  "source_post": {
    "tg_message_id": 123,
    "text": "truncated text",
    "message_date": "iso_datetime",
    "age_minutes": 37,
    "matched_triggers": ["crm migration"]
  },
  "reply_context": "truncated parent text or null",
  "style": {
    "global": ["string"],
    "account": ["string"],
    "community": ["string"],
    "topic": ["string"]
  },
  "community_context": {
    "latest_summary": "string|null",
    "dominant_themes": ["string"]
  }
}
```

Rules for input:

- No sender username.
- No sender Telegram user ID.
- No phone numbers.
- Scheduled detection must ignore messages older than the engagement account's join time when a
  joined membership timestamp is available. The app should not create fresh engagement
  opportunities from messages that were posted before the account joined the community.
- Exactly one `source_post` must be present for normal reply opportunity drafting.
- `source_post.text` maximum length is 500 characters.
- `reply_context` maximum length is 500 characters.
- `community_context.latest_summary` should be capped to 2,000 characters and must remain
  community-level.
- The legacy `messages` array may be used only as a single-item compatibility alias for the
  selected `source_post` in normal drafting, or as a broader array for observe/debug or later
  experiments. Normal reply-opportunity drafting must not include broad recent message batches.
- Maximum serialized model input target: 64 KB.

Structured output contract:

```json
{
  "should_engage": true,
  "topic_match": "topic name",
  "source_tg_message_id": 123,
  "reason": "The group is discussing CRM alternatives.",
  "reply_strategy": "Add a short tradeoff-focused reply about migration effort.",
  "moment_strength": "good",
  "timeliness": "fresh",
  "reply_value": "practical_tip",
  "suggested_reply": "Short public reply text.",
  "risk_notes": []
}
```

Output validation:

- `source_tg_message_id` must equal the selected trigger post ID.
- `topic_match` must match the selected topic name or be omitted.
- `reason` must be operator-facing and must not mention private/internal analysis.
- `reply_strategy` is optional but useful for audit; it must describe why the reply is useful, not
  how to persuade a person.
- `moment_strength` must describe the public conversation moment only: `weak`, `good`, or `strong`.
- `timeliness` must describe the source post freshness only: `fresh`, `aging`, or `stale`.
- `reply_value` must describe the proposed public contribution, such as `clarifying_question`,
  `practical_tip`, `correction`, `resource`, `other`, or `none`.
- `suggested_reply` is required only when `should_engage = true`.
- `suggested_reply` must pass normal reply validation before reply opportunity creation.
- `risk_notes` should include caveats such as "topic fit is weak", "reply may sound promotional",
  or "source post may already be answered".
### Operator Notification Contract

Detection should notify the operator when a fresh reply opportunity is created and there is enough
time left for review before `reply_deadline_at`.

Notification rules:

- Notify only after the reply opportunity row is committed.
- Do not notify for observe-mode diagnostic traces.
- Do not notify for stale opportunities.
- Include community title, topic name, source excerpt, suggested reply, freshness label, and review
  deadline.
- Do not include sender identity, phone numbers, raw prompt text, or hidden analysis internals.
- Mark `operator_notified_at` when the notification is successfully opened in the operator inbox or
  sent by the bot.
