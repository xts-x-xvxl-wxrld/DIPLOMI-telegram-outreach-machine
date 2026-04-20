# Engagement Spec

## Purpose

Engagement is an optional, operator-controlled module for joining approved Telegram communities and
participating in public discussion when an approved topic is already being discussed.

The module is separate from discovery, collection, expansion, and analysis. It may read community
collection artifacts and analysis summaries, but it owns all outbound Telegram behavior, review
state, rate limits, and audit logs.

The safe default is human-in-the-loop:

```text
detect relevant discussion
  -> create a reply opportunity
  -> operator reviews
  -> approved reply is sent publicly
  -> action is logged
```

Engagement is not part of the seed-first discovery MVP unless the operator explicitly enables it for
a community and account.

Admin prompt controls, engagement-specific target intake, per-community style rules, and editable
reply review are specified separately in `wiki/spec/engagement-admin-control-plane.md`.
Those controls are now part of the active engagement implementation: detection records the prompt
profile/version summary used for drafting, and reply opportunity approval uses the latest validated
`final_reply` when an operator edits a reply before approval.

In plain product terms: the engagement module may participate only in groups or channels where an
approved engagement account is already allowed to operate. It does not discover people to contact.
It watches approved public discussion surfaces, drafts reply opportunities from configured
instructions, and sends only through the approval and rate-limit path described below.

## Terminology

Operator-facing engagement language should use **reply opportunity**, not `candidate`. A reply
opportunity is a time-sensitive opening to answer a specific public message in an approved
community. It has a source post, topic, suggested reply, review state, and send deadline.

The current database and API still use `engagement_candidates`, `candidate_id`, and
`EngagementCandidateOut` for compatibility with implemented code. New UI copy, docs, and future API
aliases should prefer `reply opportunity`. A later migration may rename storage and endpoints, but
until then the spec treats `candidate` as a legacy implementation name for a reply opportunity.

Collection and detection are separate:

| Step | What it does | What it must not do |
|---|---|---|
| Collection | Reads approved communities and stores bounded public artifacts such as recent message samples, metadata, and optional raw messages. | Decide whether to engage, call OpenAI for engagement, draft replies, notify operators, join, or send. |
| Detection | Reads collection artifacts for approved engagement targets, applies topic/timing/policy gates, may call OpenAI, and creates reply opportunities for review. | Scrape Telegram directly in MVP, collect broad history, join, send, or mutate collection/analysis state. |

## Non-Goals

- No direct messages to community members.
- No person-level persuasion scores, user rankings, or outreach priority lists.
- No covert identity behavior or fake organic consensus.
- No vote, reaction, subscriber, member, or view manipulation.
- No bulk joining or mass posting.
- No posting in communities that have not been explicitly approved for engagement.
- No regular seed add/import may automatically approve a community for engagement.
- No business logic in collection workers.
- No OpenAI calls in collection, discovery, seed resolution, or expansion.

## Ethics And Platform Rules

Telegram user accounts managed through Telethon are scarce operational identities. Engagement must
be transparent, sparse, and useful.

Baseline rules:

- Use dedicated Telegram accounts, not the operator's main personal account.
- Clearly configure the account identity before use; do not impersonate unrelated people.
- Prefer replies to existing discussion over unsolicited top-level posts.
- Keep all engagement public inside approved communities.
- Never contact individual users privately.
- Do not generate deceptive claims of personal experience, affiliation, popularity, urgency, or
  consensus.
- Prefer no reply when the value of a reply is weak or ambiguous.
- Respect Telegram flood-wait behavior and community moderation norms.
- Keep an audit trail of every join, draft, approval, rejection, send, skip, and failure.

## Inputs

Engagement reads:

- `communities` rows with operator-approved engagement settings.
- `telegram_accounts` rows through the account manager.
- `collection_runs.analysis_input` for compact recent message samples.
- `messages` only when raw message storage is enabled for that community.
- `analysis_summaries` for community-level context.
- `engagement_topics` configured by the operator.

Engagement writes:

- community engagement settings
- account membership state
- reply opportunities
- outbound action audit logs

## Contract Overview

Engagement has six moving parts:

| Part | Owns | Must not own |
|---|---|---|
| Settings | Per-community engagement policy, rate limits, quiet hours | Telegram network calls |
| Topics | Operator-defined topic triggers and reply guidance | Community relevance scoring |
| Memberships | Which managed account joined which community | Account health decisions beyond release outcome |
| Detection | Topic matching, reply opportunity drafting, operator notification | Sending messages or joining groups |
| Review | Operator approval, rejection, and optional final text | Telethon sending |
| Send | Final preflight checks, public reply send, audit log | Reply opportunity generation or topic scoring |

Implementation roots should follow this split:

```text
backend/services/community_engagement.py       -- database state transitions and validation
backend/workers/community_join.py             -- join orchestration and account release
backend/workers/engagement_detect.py          -- detection orchestration and model calls
backend/workers/engagement_send.py            -- send orchestration and account release
backend/workers/telegram_engagement.py        -- fakeable Telethon adapter
backend/api/routes/engagement.py              -- operator API only, no Telethon
bot/main.py + bot/api_client.py               -- operator controls
```

## Durable Status Values

Status fields are PostgreSQL `text` columns in the MVP, validated by Python enums and API schemas.

### Engagement Setting Modes

Allowed `community_engagement_settings.mode` values:

- `disabled`
- `observe`
- `suggest`
- `require_approval`
- `auto_limited`

MVP allowed modes:

- `disabled`
- `observe`
- `suggest`
- `require_approval`

`auto_limited` is reserved and must be rejected by the API until a later plan explicitly enables
automatic sending.

### Membership Statuses

Allowed `community_account_memberships.status` values:

- `not_joined`
- `join_requested`
- `joined`
- `failed`
- `left`
- `banned`

State transitions:

```text
not_joined -> join_requested -> joined
not_joined -> join_requested -> failed
joined -> left
joined -> banned
failed -> join_requested
left -> join_requested
```

`banned` is terminal until the operator manually resets the row.

### Reply Opportunity Statuses

Allowed `engagement_candidates.status` values. The table name is legacy; these are reply
opportunity statuses:

- `needs_review`
- `approved`
- `rejected`
- `sent`
- `expired`
- `failed`

State transitions:

```text
needs_review -> approved
needs_review -> rejected
needs_review -> expired
approved -> sent
approved -> failed
approved -> expired
failed -> approved
```

Rules:

- `sent`, `rejected`, and `expired` are terminal for normal API operations.
- A failed reply opportunity may be re-approved by the operator when the failure was operational.
- The API must reject approval of expired reply opportunities.

### Action Statuses

Allowed `engagement_actions.status` values:

- `queued`
- `sent`
- `failed`
- `skipped`

State transitions:

```text
queued -> sent
queued -> failed
queued -> skipped
```

Action rows are append-only for audit. Status may be updated on the same action row while the worker
is executing, but completed action rows must not be rewritten except for an explicit operator
correction workflow.

## Global Invariants

These rules apply across all engagement code:

- No API route calls Telethon.
- No collection worker imports engagement services or writes engagement tables.
- No engagement worker writes `community_members.event_count` or `analysis_summaries`.
- No engagement prompt includes phone numbers or unnecessary sender identity.
- No reply opportunity is sent unless its status is `approved`.
- No reply opportunity is sent when `require_approval = false` in MVP because that setting is rejected.
- No send occurs when the community settings row is missing or disabled.
- No send occurs when `allow_post = false`.
- No join occurs when `allow_join = false`.
- No join, detection, or send occurs unless an approved `engagement_targets` row grants the matching
  `allow_join`, `allow_detect`, or `allow_post` permission.
- No direct messages are supported by any payload, adapter, or API route.
- Outbound text must be stored exactly as sent.
- Each worker must be idempotent enough to tolerate RQ retry without duplicate sends.

## Community Settings

Each community has explicit engagement settings. Absence of settings means engagement is disabled.

Recommended table: `community_engagement_settings`

```sql
id                         uuid PRIMARY KEY
community_id               uuid NOT NULL REFERENCES communities(id)
mode                       text NOT NULL DEFAULT 'suggest'
                           -- disabled | observe | suggest | require_approval | auto_limited
allow_join                 boolean NOT NULL DEFAULT false
allow_post                 boolean NOT NULL DEFAULT false
reply_only                 boolean NOT NULL DEFAULT true
require_approval           boolean NOT NULL DEFAULT true
max_posts_per_day          int NOT NULL DEFAULT 1
min_minutes_between_posts  int NOT NULL DEFAULT 240
quiet_hours_start          time
quiet_hours_end            time
assigned_account_id        uuid REFERENCES telegram_accounts(id)
created_at                 timestamptz NOT NULL DEFAULT now()
updated_at                 timestamptz NOT NULL DEFAULT now()

UNIQUE (community_id)
```

Mode meanings:

| Mode | Meaning |
|---|---|
| `disabled` | Do not join, detect, draft, or send. |
| `observe` | Detect topic moments but do not draft replies. |
| `suggest` | Draft reply opportunities for operator review. |
| `require_approval` | Operator approval is required before every send. |
| `auto_limited` | Future mode for tightly capped automatic replies after policy is proven safe. |

MVP default:

```text
mode = suggest
allow_join = false
allow_post = false
reply_only = true
require_approval = true
max_posts_per_day = 1
min_minutes_between_posts = 240
```

Validation contract:

- `community_id` must reference an existing community.
- `mode = disabled` forces `allow_join = false` and `allow_post = false`.
- MVP rejects `mode = auto_limited`.
- MVP rejects `require_approval = false`.
- MVP rejects `reply_only = false`.
- `max_posts_per_day` must be between 0 and 3 in MVP.
- `min_minutes_between_posts` must be at least 60 in MVP.
- If one quiet-hour value is provided, both must be provided.
- `assigned_account_id`, when provided, must reference an account that is not banned.
- `assigned_account_id`, when provided, must reference an account in the `engagement` account pool
  defined by `wiki/spec/telegram-account-pools.md`.
- Only communities with `status IN ('approved', 'monitoring')` may enable `allow_join` or
  `allow_post`.

Service contract:

```python
def get_engagement_settings(db, community_id: UUID) -> EngagementSettingsView:
    ...

def upsert_engagement_settings(
    db,
    *,
    community_id: UUID,
    payload: EngagementSettingsUpdate,
    updated_by: str,
) -> EngagementSettingsView:
    ...
```

`get_engagement_settings` returns a disabled synthetic view when no row exists. It should not create
a database row just because the operator viewed settings.

## Account Memberships

The app must track which managed account has joined which community. It should not join every
account to every community.

Recommended table: `community_account_memberships`

```sql
id                   uuid PRIMARY KEY
community_id          uuid NOT NULL REFERENCES communities(id)
telegram_account_id   uuid NOT NULL REFERENCES telegram_accounts(id)
status                text NOT NULL DEFAULT 'not_joined'
                      -- not_joined | join_requested | joined | failed | left | banned
joined_at             timestamptz
last_checked_at       timestamptz
last_error            text
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (community_id, telegram_account_id)
```

Rules:

- One account is selected for a community unless the operator explicitly changes it.
- Joining uses the account manager with an engagement purpose.
- `FloodWaitError` marks the account rate-limited through the account manager.
- Community-level access failures update the membership row, not the account health, unless the
  error is account-level.

Selection contract:

1. If `community_engagement_settings.assigned_account_id` is set, use that account only if it is in
   the `engagement` account pool.
2. Else if a `joined` membership already exists for the community with an `engagement` account, use
   that account.
3. Else acquire any healthy `engagement` account through the account manager.
4. After a successful join, write or update the membership row.

The first implementation should prefer one joined account per community. Multiple joined accounts
are allowed in the schema for future manual operator actions, but workers must not create them
automatically.

Service contract:

```python
def mark_join_requested(
    db,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
) -> CommunityAccountMembership:
    ...

def mark_join_result(
    db,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
    status: Literal["joined", "failed", "banned"],
    joined_at: datetime | None,
    error_message: str | None,
) -> CommunityAccountMembership:
    ...

def get_joined_membership_for_send(
    db,
    *,
    community_id: UUID,
) -> CommunityAccountMembership | None:
    ...
```

## Topics

Engagement topics define when the app should consider a public reply.

Operator-facing topic guidance has two required parts:

| Field | Question it answers | Stored in MVP |
|---|---|---|
| Conversation target | What kind of conversation are we looking for? | `description`, `trigger_keywords`, and `negative_keywords` |
| Position guidance | What position should we take? | `stance_guidance` |

The UI should present these as two distinct topic-guidance values even if the first implementation
stores the conversation target across the existing description and keyword fields. The conversation
target is used to identify opportunities; the position guidance is used when deciding what a useful
reply would say.

Recommended table: `engagement_topics`

```sql
id                    uuid PRIMARY KEY
name                  text NOT NULL
description           text
stance_guidance       text NOT NULL
trigger_keywords      text[] NOT NULL DEFAULT '{}'
negative_keywords     text[] NOT NULL DEFAULT '{}'
example_good_replies  text[] NOT NULL DEFAULT '{}'
example_bad_replies   text[] NOT NULL DEFAULT '{}'
active                boolean NOT NULL DEFAULT true
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()
```

Topic guidance should describe the desired conversation and how to be useful inside it, not how to
manipulate the group.

Good guidance:

```text
Conversation target: People comparing open-source CRM tools, asking about CRM migration, or
discussing practical CRM evaluation criteria.

Position guidance: Be factual, brief, and non-salesy. Mention tradeoffs such as setup effort,
integrations, export access, team adoption, and data quality.
```

Bad guidance:

```text
Convince users that our product is best and make it look like the whole group agrees.
```

Validation contract:

- `name` is required and should be unique case-insensitively.
- `stance_guidance` is required.
- `trigger_keywords` must contain at least one item for active topics in MVP.
- Keywords are case-folded and trimmed before storage.
- `example_bad_replies` should be used in prompts as negative examples only.
- Disallowed guidance includes instructions to deceive, impersonate, harass, target individuals,
  generate fake consensus, or evade moderation.

Service contract:

```python
def create_topic(db, *, payload: EngagementTopicCreate) -> EngagementTopicView:
    ...

def update_topic(db, *, topic_id: UUID, payload: EngagementTopicUpdate) -> EngagementTopicView:
    ...

def list_active_topics(db) -> list[EngagementTopic]:
    ...
```

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

## Jobs

### `community.join`

Joins one approved community with one managed Telegram account.

Payload:

```json
{
  "community_id": "uuid",
  "telegram_account_id": "uuid-or-null",
  "requested_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="engagement_join")`

Rules:

- `allow_join` must be true.
- An approved engagement target with `allow_join = true` must exist for the community.
- The community must be approved for engagement.
- Private invite links are out of scope for MVP.
- Do not join multiple accounts unless requested by the operator.
- Respect FloodWait and account health mapping.

Worker preflight:

1. Load community.
2. Load settings; skip if missing, disabled, or `allow_join = false`.
3. Verify an approved engagement target with `allow_join = true`.
4. Select or acquire an account according to the membership selection contract.
5. Mark membership `join_requested`.
6. Resolve the Telegram entity.
7. Join or confirm already joined.
8. Mark membership `joined` or `failed`.
9. Write an `engagement_actions` audit row with `action_type = join`.
10. Release account in `finally`.

Telethon adapter contract:

```python
@dataclass
class JoinResult:
    status: Literal["joined", "already_joined", "inaccessible"]
    joined_at: datetime | None
    error_message: str | None = None

class TelegramEngagementAdapter:
    async def join_community(self, *, session_file_path: str, community: Community) -> JoinResult:
        ...
```

### `engagement.detect`

Detects relevant topic moments and creates reply opportunities.

Payload:

```json
{
  "community_id": "uuid",
  "window_minutes": 60,
  "requested_by": "telegram_user_id_or_operator|null"
}
```

Reads:

- active engagement settings
- active engagement topics
- compact recent message samples from collection artifacts
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
- Use collection samples to select one or more precise trigger posts, then cap draft-generation
  input to the selected trigger, optional reply context, topic guidance, style rules, and
  community-level context.
- For normal scheduled detection, the model input must contain exactly one selected trigger post as
  `source_post`. Broad recent `messages` arrays are allowed only for observe/debug experiments.
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
8. Load recent compact message samples.
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
| `no_recent_samples` | Collection produced no usable samples for the detection window. |
| `no_trigger_opportunities` | Samples did not pass deterministic trigger selection. |
| `outside_response_window` | Matching samples were too new or too old for scheduled drafting. |
| `quiet_hours` | Detection was suppressed by configured quiet hours. |
| `active_reply_opportunity_exists` | A reviewable reply opportunity already exists for the same source/topic/community flow. |

Legacy implementations may still emit `no_trigger_candidates` and `active_candidate_exists` until
the code-level rename is complete. New code should emit the reply-opportunity names above.

### Detection Sample Contract

Detection reads public collection artifacts and normalizes them into bounded samples before any
matching or model call.

```json
{
  "tg_message_id": 123,
  "text": "truncated public message text",
  "message_date": "iso_datetime",
  "reply_to_tg_message_id": 122,
  "reply_context": "truncated parent text or null",
  "is_replyable": true,
  "source": "collection_run.analysis_input"
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
- The legacy `messages` array may be used only for observe/debug or later experiments; normal
  reply opportunity drafting must not include broad recent message batches.
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

### `engagement.send`

Sends one approved public reply.

Payload:

```json
{
  "candidate_id": "uuid",
  "approved_by": "telegram_user_id_or_operator"
}
```

`candidate_id` is the legacy API field name for the approved reply opportunity ID.

Uses:

- `account_manager.acquire_account(purpose="engagement_send")`

Rules:

- Reply opportunity must be `approved`.
- Community settings must allow posting.
- An approved engagement target with `allow_post = true` must exist for the community.
- `require_approval` must be satisfied.
- The account must have joined the community.
- The joined membership account must be in the `engagement` account pool.
- Daily and spacing limits must pass for the account and community.
- MVP sends replies only; top-level posts are future/optional.
- Store an `engagement_actions` row whether the result is sent, failed, or skipped.

Worker preflight:

1. Load reply opportunity with topic and community.
2. Skip if reply opportunity is not approved.
3. Skip if reply opportunity is expired or past `reply_deadline_at`.
4. Load settings; skip if missing, disabled, or `allow_post = false`.
5. Verify an approved engagement target with `allow_post = true`.
6. Reject top-level send if `reply_only = true` and `source_tg_message_id` is missing.
7. Load joined membership; skip if none exists.
8. Check community and account send limits.
9. Create or resume `engagement_actions` row with idempotency key.
10. Acquire the membership account with `purpose = engagement_send`.
11. Send reply through Telethon.
12. Mark action sent and reply opportunity sent.
13. Release account in `finally`.

Rate-limit contract:

- Count only `engagement_actions` with `status = sent`.
- Community limit uses `community_id` and a rolling 24-hour window.
- Account limit uses `telegram_account_id` and a rolling 24-hour window.
- Spacing limit uses the latest sent action for the community and for the account; both must pass.
- Failed or skipped actions do not consume rate-limit quota.

Telethon adapter contract:

```python
@dataclass
class SendResult:
    sent_tg_message_id: int
    sent_at: datetime

class TelegramEngagementAdapter:
    async def send_public_reply(
        self,
        *,
        session_file_path: str,
        community: Community,
        reply_to_tg_message_id: int,
        text: str,
    ) -> SendResult:
        ...
```

Error mapping:

| Error | Account outcome | Action status | Reply opportunity status |
|---|---|---|---|
| FloodWait | rate_limited | failed | approved |
| banned/deauthorized | banned | failed | failed |
| transient network | error | failed | approved |
| community inaccessible | success | skipped | approved |
| message no longer replyable | success | skipped | expired |
| validation/safety failure | success | skipped | failed |

## Detection And Drafting Prompt Rules

The engagement detector may use OpenAI to decide whether a message sample is a good moment for a
reply and to draft that reply.

### Instruction Model

The message-generation agent must be instructed through durable admin configuration, not ad hoc
worker code. The active prompt profile is editable through the engagement bot controls, and every
edit should create an immutable prompt-profile version before activation.

Draft generation should use a lean prompt. The worker assembles the final drafting prompt from
these layers:

```text
immutable safety floor
  + active prompt profile
  + topic guidance and examples
  + global/account/community/topic style rules
  + community-level summary
  + selected source post or trigger excerpt
  + reply target context, when needed
```

Recent public message batches may be used for opportunity detection, but they should not be dumped
into the draft-generation prompt by default. The draft prompt should receive the minimum context
needed to write a focused public reply.

The operator-facing instruction controls should answer five questions:

| Question | Stored as | Example |
|---|---|---|
| What kind of conversation are we looking for? | topic conversation target, trigger keywords, negative keywords | notice CRM migration discussions; ignore hiring posts |
| What position should it take? | topic `stance_guidance` | be practical, compare tradeoffs, avoid sales pressure |
| How should it sound here? | style rules | brief, transparent, no links unless asked |
| What is allowed to be claimed? | prompt profile and account/community style rules | may say "we maintain a tool"; must not claim to be a customer |
| What should it avoid? | bad examples, validation, and safety floor | no DMs, no urgency, no fake consensus, no personal profiling |

Style rules answer one primary user question: how should this account sound in this community?
They belong in the rendered user prompt alongside topic guidance and examples, not in the immutable
safety floor. Community, account, and topic style rules may make replies shorter, calmer, more
transparent, or more specific to the local discussion.

The editable prompt profile can tune the model's role, reasoning rubric, output format, and tone.
It cannot override hard product rules. If a prompt profile, topic, or style rule conflicts with
reply-only mode, approval requirements, no-DM rules, link validation, or rate limits, backend
validation and worker preflight win.

The generator should behave like a helpful public participant for the configured operator account:

- Reply only when the current discussion already creates a relevant opening.
- Add one useful thought, question, comparison, caveat, or resource.
- Prefer short replies that fit the community's current tone.
- Say nothing when the reply would be generic, promotional, late, or off-topic.
- Never invent personal experience, customer status, moderator authority, affiliation, statistics,
  scarcity, urgency, or consensus.
- Never target a named individual, rank people, or suggest moving the conversation to DMs.
- Avoid links by default; allow links only when the topic or style policy permits them and the
  operator approves the final reply.

Recommended generated reply shape:

```text
1-3 sentences
directly references the public topic being discussed
adds practical value or a clarifying question
does not ask for private contact
does not sound like an advertisement
```

The model must always be allowed to return `should_engage = false`. A "no reply" decision is a
successful outcome when the moment is weak, stale, risky, off-topic, already answered, or too old to
join naturally.

Immutable safety floor:

```text
No DMs.
No fake consensus.
No impersonation.
No auto-send.
```

Other research and product boundaries, such as no person-level scores and no hidden collection
internals, remain enforced by database design, analysis boundaries, validation, and worker preflight
rather than being expanded into a noisy immutable drafting prompt.

Structured output:

```json
{
  "should_engage": true,
  "topic_match": "topic name",
  "reason": "The group is discussing CRM alternatives.",
  "suggested_reply": "Short public reply text.",
  "risk_notes": []
}
```

If `should_engage = false`, the worker should not create a reply opportunity unless the operator
requested a debug trace.

Reply validation rules:

- Maximum 800 characters in MVP.
- No request to DM.
- No claim that the account is a customer, founder, moderator, or ordinary community member unless
  explicitly configured as true for that account.
- No unverifiable statistics.
- No hostile, harassing, or manipulative language.
- No hidden disclosure of collection or analysis internals.
- No links unless the topic policy allows links and the operator approves the final reply.

## API Surface

Initial endpoints:

```http
GET  /api/communities/{community_id}/engagement-settings
PUT  /api/communities/{community_id}/engagement-settings
POST /api/communities/{community_id}/join-jobs
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
- The send endpoint enqueues a job; it should not call Telethon directly.
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
```

`/engagement_candidates` and `eng:cand:*` are legacy command/callback names. Bot copy should say
reply opportunity.

Inline review cards should show:

- community title
- matched topic
- capped source excerpt
- suggested reply
- approve/send button
- reject button

Editing suggested replies may be added after the basic approve/reject flow.

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

## Scheduling

Engagement detection should run after collection for timely communities and can also run on a
separate low-frequency scheduler tick as a fallback sweep.

### Monitoring Model

Monitoring is a two-stage process:

```text
collection watches approved communities
  -> collection writes compact recent public samples
  -> engagement.detect is queued from fresh collection completion when engagement is enabled
  -> engagement scheduler also checks eligible communities as a fallback sweep
  -> engagement.detect finds fresh post-join trigger messages
  -> engagement.detect drafts from the selected trigger and community context
  -> reply opportunities wait for operator review
  -> fresh reply opportunities notify the operator
```

Collection owns Telegram reads and durable public artifacts. Detection owns engagement decisions.
The engagement scheduler does not directly scrape Telegram in the MVP. It reads durable collection
artifacts or opt-in stored messages. This keeps outbound behavior separate from collection and
prevents the engagement module from becoming an always-on raw chat listener.

Eligibility for a scheduled detection run:

- The community has engagement settings in `observe`, `suggest`, or `require_approval` mode.
- An approved engagement target grants `allow_detect`.
- A completed collection run exists inside the configured detection window.
- There is no active reply opportunity already waiting for the same community review flow.
- The current time is outside configured quiet hours.

Opportunity detection should be precise before invoking the drafting model. The first-pass selector
should use deterministic signals such as:

- topic trigger keyword or phrase matches
- negative keyword exclusions
- message age
- whether the message was posted after the engagement account joined
- whether the message is a replyable group message
- dedupe against active reply opportunities and recent sent actions

Keyword matches are a trigger opportunity, not a send decision. A match should identify a source
post for review, then the drafting model decides whether the moment is strong enough to create a
reply opportunity.

Messages posted before the engagement account joined the community must not trigger new engagement
reply opportunities. They may inform a community-level summary, but the bot should not join a group and
reply to old pre-join discussions as if it had been organically present.

Freshness SLO:

- For engagement-enabled communities with fresh collection artifacts, a qualifying source post
  should produce a committed reply opportunity and operator notification within 10 minutes of
  collection completion.
- The SLO begins when collection has produced a usable sample; collection latency is measured
  separately.
- If the detector misses the SLO, it may still create the opportunity while the source post is before
  `reply_deadline_at`, but the opportunity should be labeled `aging`.
- After `reply_deadline_at`, scheduled detection must skip creating a sendable reply opportunity.

Target response timing:

- Prefer opportunities where the trigger message is 15 to 60 minutes old.
- Skip or downgrade messages younger than 15 minutes unless the operator manually forces detection;
  this avoids instant bot-like replies.
- Skip scheduled draft creation for trigger messages older than 60 minutes by default.
- Manual detection may inspect a wider window for diagnosis, but send preflight should still treat
  stale reply opportunities conservatively.

Default cadence:

| Setting | Default | Meaning |
|---|---:|---|
| `ENGAGEMENT_COLLECTION_DETECT_ON_COMPLETE` | true | queue detection after successful collection for engagement-enabled communities |
| `ENGAGEMENT_ACTIVE_COLLECTION_INTERVAL_SECONDS` | 600 | target compact collection cadence for engagement-enabled communities |
| `ENGAGEMENT_SCHEDULER_INTERVAL_SECONDS` | 3600 | fallback scheduler wakes roughly once per hour |
| `ENGAGEMENT_DETECTION_WINDOW_MINUTES` | 60 | detection considers the latest hour of collected samples |
| `ENGAGEMENT_REPLY_DEADLINE_MINUTES` | 90 | send preflight rejects replies after this source-post age |
| `max_posts_per_day` | 1 | maximum sent replies per community and account in a rolling 24-hour window |
| `min_minutes_between_posts` | 240 | minimum spacing between sent replies for both community and account |

Manual detection can be operator-triggered for an approved target and may use a custom
`window_minutes`, but it still uses the same target permission, topic, prompt, privacy, and
reply opportunity creation rules.

### Send Timing Model

Sending is intentionally separated from monitoring. Detection may create reply opportunities, but it
must not queue `engagement.send` in the MVP.

A public reply may be sent only when all of these are true:

- The reply opportunity is still before `reply_deadline_at` and has status `approved`.
- The approved `final_reply` passes safety and length validation.
- The community settings still allow posting and require approval.
- The engagement target grants `allow_post`.
- The selected engagement account is already joined to the community.
- Reply-only mode can be satisfied by replying to a source Telegram message.
- Quiet hours, rolling daily limits, and minimum spacing checks pass.

Timing behavior should feel sparse and human-supervised:

- Draft quickly enough that the operator can review while the discussion is still current.
- Expire stale reply opportunities rather than sending late replies into a cooled-off thread.
- Use rate limits as hard caps, not goals. The best day may still have zero sends.
- Never batch multiple sends into the same community just because multiple topics matched.
- Treat failed or skipped send attempts as audit events, not reasons to retry aggressively.

Recommended MVP:

- Only run detection for communities with engagement settings enabled.
- Queue detection after fresh collection completion for engagement-enabled communities.
- Keep hourly detection as a fallback sweep, not the primary timely path.
- Skip if there is already an active reply opportunity for the same community/topic/source.
- Skip during quiet hours if configured.
- Do not enqueue sends automatically in MVP.

Scheduler contract:

- Job ID for detection: `engagement.detect:{community_id}:{yyyyMMddHH}`.
- Scheduler reads only settings where `mode IN ('observe', 'suggest', 'require_approval')`.
- Scheduler skips communities without a completed collection run in the last configured window.
- Scheduler does not create direct send jobs.
- Manual detection uses a distinct job ID prefix so the operator can force a run.

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

## Safety Rules

- Engagement is opt-in per community.
- Human approval is required before send in MVP.
- No DMs.
- No person-level scoring.
- No hidden manipulation or fake consensus.
- No mass joining.
- No automatic posting until manual review has proven the topic policy and rate limits.
- All outbound actions are auditable.
- Collection remains read-only and must not send messages.
- Analysis remains community-level and must not produce outreach instructions for individuals.
