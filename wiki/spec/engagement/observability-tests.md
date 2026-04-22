# Engagement Observability And Tests

Operational metrics, logs, and behavior tests required for engagement changes.

## Observability

Worker job metadata should include:

```json
{
  "job_type": "engagement.detect",
  "community_id": "uuid",
  "candidate_id": "uuid|null",
  "reply_opportunity_id": "uuid|null",
  "topic_id": "uuid|null",
  "status_message": "human readable short status",
  "started_at": "iso_datetime",
  "last_heartbeat_at": "iso_datetime"
}
```

Metrics or structured logs should count:

- reply opportunities created
- reply opportunities skipped by weak topic fit
- reply opportunities skipped by dedupe
- reply opportunities notified
- reply opportunities stale before review
- joins attempted
- joins succeeded
- sends attempted
- sends succeeded
- sends skipped by preflight
- FloodWait events
- validation failures

## Testing Contract

Minimum tests for the first implementation:

- settings defaults and validation
- topic create/update validation
- membership state transitions
- reply opportunity dedupe, deadlines, and expiration
- approve/reject transitions
- send preflight skips for missing settings, disabled settings, missing approval, expired or stale
  reply opportunity, no joined membership, and rate limits
- join worker success, already joined, inaccessible community, FloodWait, and banned account paths
- detect worker no-signal and reply-opportunity-created paths with fake LLM output
- detect worker skip reasons for missing joined engagement membership, missing `joined_at`,
  disabled settings, observe mode, missing target permission, no recent samples, no trigger
  opportunities, active reply opportunity dedupe, and quiet hours
- trigger selection rejects pre-join messages, too-new messages, too-old messages, non-replyable
  messages, negative-keyword matches, missing IDs, missing timestamps, and duplicate source/topic
  opportunities
- trigger selection accepts keyword and phrase matches with deterministic ordering and caps model
  calls per topic and per community run
- draft model input contains one `source_post`, optional `reply_context`, topic guidance, style
  rules, and community summary, and does not include broad recent message batches in normal
  reply opportunity drafting
- model output validation rejects mismatched `source_tg_message_id`, missing suggested replies for
  `should_engage = true`, unsafe suggested replies, and private/internal reasons
- model output validation stores `moment_strength`, `timeliness`, and `reply_value` without creating
  person-level scores
- operator notification opens only for fresh or aging reply opportunities and records
  `operator_notified_at`
- send worker idempotency and no duplicate send on retry
- API auth and schema tests
- bot formatting/callback tests for reply opportunity cards
