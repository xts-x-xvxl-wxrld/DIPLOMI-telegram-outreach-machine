# Engagement Opportunities And Actions

Reply opportunity and outbound action contracts for human-approved public replies.

## Reply Opportunities

Detection creates a reply opportunity. Sending is a separate step.

Recommended table: `engagement_candidates`

The table name is retained for the current implementation. Semantically, each row is a reply
opportunity.

```sql
id                       uuid PRIMARY KEY
community_id             uuid NOT NULL REFERENCES communities(id)
topic_id                 uuid NOT NULL REFERENCES engagement_topics(id)
source_tg_message_id     bigint
source_excerpt           text
source_message_date      timestamptz
detected_at              timestamptz NOT NULL DEFAULT now()
detected_reason          text NOT NULL
suggested_reply          text
model                    text
model_output             jsonb
prompt_profile_id        uuid REFERENCES engagement_prompt_profiles(id)
prompt_profile_version_id uuid REFERENCES engagement_prompt_profile_versions(id)
prompt_render_summary    jsonb
risk_notes               text[] NOT NULL DEFAULT '{}'
moment_strength          text
                         -- weak | good | strong
timeliness               text
                         -- fresh | aging | stale
reply_value              text
                         -- clarifying_question | practical_tip | correction | resource | other | none
status                   text NOT NULL DEFAULT 'needs_review'
                         -- needs_review | approved | rejected | sent | expired | failed
final_reply              text
reviewed_by              text
reviewed_at              timestamptz
review_deadline_at       timestamptz
reply_deadline_at        timestamptz
operator_notified_at     timestamptz
expires_at               timestamptz NOT NULL
created_at               timestamptz NOT NULL DEFAULT now()
updated_at               timestamptz NOT NULL DEFAULT now()
```

Rules:

- Reply opportunity rows must not include unnecessary Telegram user identity.
- `source_excerpt` must be capped and sanitized like analysis input message examples.
- `reply_deadline_at` is the conversation deadline after which sending would feel late.
- `expires_at` is the hard cleanup deadline for stale review items, usually within 24 hours.
- The same source message should not generate duplicate active reply opportunities for the same topic.
- The suggested reply is a draft, not authorization to send.
- Operator-facing views should show `fresh`, `aging`, or `stale` from the source post age and
  `reply_deadline_at`.
- Scheduled detection should create only fresh or aging reply opportunities. Stale moments should be
  skipped unless the operator explicitly requested a diagnostic/manual run.

Creation contract:

- `source_excerpt` maximum length is 500 characters.
- `suggested_reply` maximum length is 800 characters in MVP.
- `source_message_date` stores the source post timestamp used for all freshness decisions.
- `detected_at` stores when the engagement detector decided to create the reply opportunity.
- `detected_reason` must be plain-language and operator-facing.
- `model_output` stores compact structured output, not full prompts or raw message batches.
- `prompt_render_summary` stores compact prompt provenance, not full raw prompt text.
- `risk_notes` stores model or rule-based caveats for operator review.
- `moment_strength` describes only the public conversation moment, never a person.
- `timeliness` describes whether the reply can still land naturally: `fresh`, `aging`, or `stale`.
- `reply_value` describes the kind of useful contribution the reply would make.
- `review_deadline_at` should leave enough time for the operator to approve while the source post is
  still fresh.
- `reply_deadline_at` should normally be no later than 90 minutes after `source_message_date` in MVP.
- `expires_at` defaults to 24 hours after creation for cleanup, but send preflight must use
  `reply_deadline_at` for conversation freshness.
- If raw message storage is disabled, the reply opportunity may reference only source message IDs
  included in compact collection artifacts.

Deduplication contract:

- There may be only one active reply opportunity for `(community_id, topic_id, source_tg_message_id)`
  where status is `needs_review` or `approved`.
- If `source_tg_message_id` is null, dedupe by `(community_id, topic_id, source_excerpt hash)` in
  service code.
- Expired, rejected, sent, and failed reply opportunities do not block future reply opportunities.

Review contract:

```python
def approve_candidate(
    db,
    *,
    candidate_id: UUID,
    approved_by: str,
    final_reply: str | None = None,
) -> EngagementCandidateView:
    ...

def reject_candidate(
    db,
    *,
    candidate_id: UUID,
    rejected_by: str,
    reason: str | None = None,
) -> EngagementCandidateView:
    ...

def expire_stale_candidates(db, *, now: datetime) -> int:
    ...
```

Approval rules:

- Reply opportunity must be `needs_review` or `failed`.
- Reply opportunity must not be expired.
- Reply opportunity must not be past `reply_deadline_at`.
- `final_reply` defaults to `suggested_reply`.
- Final text must pass the same safety and length validation as generated text.
- Approving does not enqueue send automatically unless the API endpoint explicitly combines
  approve-and-send in a later slice.

## Outbound Actions

Every join or post attempt writes an audit row.

Recommended table: `engagement_actions`

```sql
id                       uuid PRIMARY KEY
candidate_id              uuid REFERENCES engagement_candidates(id)
community_id              uuid NOT NULL REFERENCES communities(id)
telegram_account_id       uuid NOT NULL REFERENCES telegram_accounts(id)
action_type               text NOT NULL
                         -- join | reply | post | skip
status                    text NOT NULL DEFAULT 'queued'
                         -- queued | sent | failed | skipped
idempotency_key           text UNIQUE
outbound_text             text
reply_to_tg_message_id    bigint
sent_tg_message_id        bigint
scheduled_at              timestamptz
sent_at                   timestamptz
error_message             text
created_at                timestamptz NOT NULL DEFAULT now()
updated_at                timestamptz NOT NULL DEFAULT now()
```

Audit rules:

- Store the exact outbound text that was approved and sent.
- Store failures and skips with clear reasons.
- Do not delete audit rows as part of normal operation.
- Operator edits to suggested replies should produce an auditable final outbound text.

Idempotency contract:

- `engagement.send` must create an action row before calling Telethon.
- `idempotency_key` for sends should be `engagement.send:{candidate_id}` while legacy identifiers
  remain in use.
- If a retry sees an existing `sent` action for the reply opportunity, it must mark the reply
  opportunity `sent` and skip network calls.
- If a retry sees an existing `queued` action with no terminal status, it may resume that action.
- If Telethon sends but the worker crashes before marking success, the next retry must avoid a
  second send when the adapter can confirm the sent message. If confirmation is not possible, the
  worker must fail closed and require operator intervention.
