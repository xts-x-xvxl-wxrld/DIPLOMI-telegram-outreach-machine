# Engagement Detection And Trigger Selection

Detailed detection orchestration, sample, and trigger selection contracts.

### `engagement.detect`

Detects relevant topic moments and creates reply opportunities.

Payload:

```json
{
  "community_id": "uuid",
  "collection_run_id": "uuid|null",
  "window_minutes": 60,
  "requested_by": "telegram_user_id_or_operator|null"
}
```

Reads:

- active engagement settings
- active engagement topics
- exact new-message engagement batches from collection artifacts
- compact recent message samples as a fallback or diagnostic source
- optional community analysis summaries

May call:

- OpenAI, only inside this engagement worker

Model configuration:

- `OPENAI_ENGAGEMENT_MODEL` selects the drafting/detection model and defaults to the same
  lightweight model used for brief extraction unless overridden.

Writes:

- `engagement_candidates` rows, semantically reply opportunities

Rules:

- Do not send messages.
- An approved engagement target with `allow_detect = true` must exist for the community.
- Reply-opportunity-creating scheduled detection requires a joined engagement account membership with
  `joined_at` available. Manual diagnostic detection may explain that a community has signal before
  joining, but it must not create a sendable reply opportunity from pre-join messages.
- Do not score or rank people.
- Prefer no reply opportunity when topic fit is weak.
- Deduplicate active reply opportunities by community, topic, and source message.
- Prefer the exact engagement batch from `collection_run_id` when provided.
- Use collection message batches to select one or more precise trigger posts, then cap
  draft-generation input to the selected trigger, optional reply context, topic guidance, style
  rules, and community-level context.
- For normal scheduled detection, the model input must contain exactly one selected trigger post as
  `source_post`.
- A legacy `messages` alias may contain only that same selected source post for template
  compatibility during rollout. Broad recent message batches are allowed only for observe/debug
  experiments and must not be used in normal reply-opportunity drafting.
- Detection should surface reviewable opportunities quickly enough for an operator to respond while
  the discussion is active. When a fresh collection artifact is available for an engagement-enabled
  community, the target SLO is to create and notify on a qualifying reply opportunity within 10
  minutes of collection completion.

Worker preflight:

1. Load community.
2. Load settings; skip if mode is `disabled` or settings are missing.
3. Skip if mode is `observe` after writing optional debug logs only; no reply opportunity is created
   in MVP.
4. Verify an approved engagement target with `allow_detect = true`.
5. Load joined engagement membership for the community.
6. Build a detection window using join time, response timing limits, and requested window.
7. Load active topics.
8. Load the collection-run engagement batch when `collection_run_id` is provided; otherwise load
   recent stored messages or compact collection artifacts for the requested window.
9. Select trigger opportunities with deterministic matching and filtering.
10. Build one lean model input per topic/source trigger.
11. Call OpenAI only for selected topic/source triggers.
12. Validate structured output.
13. Create a reply opportunity when `should_engage = true`.
14. Notify the operator when the reply opportunity is fresh enough to review.

Scheduled skip reasons should be stable strings:

| Reason | Meaning |
|---|---|
| `community_not_found` | The community row does not exist. |
| `engagement_disabled` | Settings are missing or disabled. |
| `observe_mode` | Settings are observe-only, so no reply opportunity should be created. |
| `engagement_target_detect_not_approved` | The target does not grant detection permission. |
| `no_joined_engagement_membership` | No engagement-pool account is joined to the community. |
| `missing_joined_at` | Joined membership exists but lacks a join timestamp for post-join filtering. |
| `no_active_topics` | No active engagement topics exist. |
| `no_recent_samples` | Collection produced no usable messages for the detection window. |
| `collection_run_not_found` | The referenced collection run does not exist or belongs to another community. |
| `no_trigger_opportunities` | Samples did not pass deterministic trigger selection. |
| `outside_response_window` | Matching samples were too new or too old for scheduled drafting. |
| `quiet_hours` | Detection was suppressed by configured quiet hours. |
| `active_reply_opportunity_exists` | A reviewable reply opportunity already exists for the same source/topic/community flow. |

Legacy implementations may still emit `no_trigger_candidates` and `active_candidate_exists` until
the code-level rename is complete. New code should emit the reply-opportunity names above.
### Detection Sample Contract

Detection reads collection artifacts and normalizes them into bounded samples before any matching or
model call. For scheduled engagement, the preferred source is the exact `engagement_messages` batch
from a completed `collection_run_id`.

```json
{
  "tg_message_id": 123,
  "text": "truncated public message text",
  "message_date": "iso_datetime",
  "reply_to_tg_message_id": 122,
  "reply_context": "truncated parent text or null",
  "is_replyable": true,
  "source": "collection_run.engagement_messages",
  "collection_run_id": "uuid"
}
```

Rules:

- `tg_message_id`, `text`, and `message_date` are required for reply-opportunity-creating scheduled
  detection.
- Samples without text are ignored.
- Samples without `tg_message_id` may be used only for observe/debug summaries, not reply
  opportunities.
- Samples without `message_date` are ignored for scheduled reply opportunity creation because timing
  cannot be enforced.
- `is_replyable` defaults to true only for group message samples with a Telegram message ID; channel
  or system-message samples should be treated as not replyable unless collection marks otherwise.
- `reply_context` is optional and capped like source text.
- Sender username, sender Telegram user ID, phone number, and private account metadata must not be
  present.

Source priority:

1. `collection_run.engagement_messages` for the collection run that just completed.
2. Stored `messages` rows inside the detection window when raw storage is enabled.
3. Compact `collection_runs.analysis_input.sample_messages` only for fallback or manual diagnostic
   detection.

Normal scheduled detection should not depend on sampled analysis input because sampled artifacts can
miss the exact source post needed for a timely reply opportunity.
### Trigger Selection Contract

Trigger selection is deterministic and happens before the drafting model. It chooses specific public
posts that are worth asking the model about.

Recommended configuration constants:

| Setting | Default | Meaning |
|---|---:|---|
| `ENGAGEMENT_TRIGGER_MIN_AGE_MINUTES` | 15 | Skip or downgrade posts newer than this in scheduled detection. |
| `ENGAGEMENT_TRIGGER_MAX_AGE_MINUTES` | 60 | Skip posts older than this in scheduled detection. |
| `ENGAGEMENT_REPLY_DEADLINE_MINUTES` | 90 | Latest source-post age where a public reply can still be sent naturally. |
| `ENGAGEMENT_MAX_TRIGGER_OPPORTUNITIES_PER_TOPIC` | 3 | Maximum source posts sent to the model per topic per run. |
| `ENGAGEMENT_MAX_REPLY_OPPORTUNITIES_PER_COMMUNITY_RUN` | 3 | Maximum reply opportunities created for one community detection job. |

Eligibility for a source post:

- Message belongs to the current collection batch or detection window.
- Message was posted after the engagement account joined the community.
- Message age is within the scheduled response window, usually 15 to 60 minutes old.
- Message is replyable.
- Message text contains at least one trigger keyword or phrase for the topic.
- Message text contains no negative keyword or phrase for the topic.
- Message does not duplicate an active reply opportunity for `(community_id, topic_id, tg_message_id)`.
- Message is not in a thread that already received a sent engagement reply in the recent cooldown
  window.

Keyword and phrase matching rules:

- Normalize by case-folding and trimming whitespace.
- Match multi-word phrases on normalized substring boundaries.
- Match single-word keywords on word boundaries when practical.
- Treat trigger keywords as OR conditions.
- Treat negative keywords as hard exclusions.
- Prefer the newest eligible message that is at least 15 minutes old.
- If multiple topics match the same message, create at most one model prompt for the highest-priority
  topic when topic priority exists; otherwise use deterministic topic ordering by name then ID.

The selector returns bounded trigger records:

```json
{
  "topic_id": "uuid",
  "source_tg_message_id": 123,
  "source_excerpt": "truncated public message text",
  "message_date": "iso_datetime",
  "age_minutes": 37,
  "matched_triggers": ["crm migration"],
  "matched_negatives": [],
  "reply_context": "truncated parent text or null",
  "selection_reason": "Matched topic trigger 'crm migration' 37 minutes after posting."
}
```

Trigger records are not reply opportunities. They only authorize a model call to decide whether
drafting is useful.
