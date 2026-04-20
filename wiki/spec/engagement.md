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
  -> draft candidate reply
  -> operator reviews
  -> approved reply is sent publicly
  -> action is logged
```

Engagement is not part of the seed-first discovery MVP unless the operator explicitly enables it for
a community and account.

Admin prompt controls, engagement-specific target intake, per-community style rules, and editable
reply review are specified separately in `wiki/spec/engagement-admin-control-plane.md`.
Those controls are now part of the active engagement implementation: detection records the prompt
profile/version summary used for drafting, and candidate approval uses the latest validated
`final_reply` when an operator edits a reply before approval.

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
- candidate engagement opportunities
- outbound action audit logs

## Contract Overview

Engagement has six moving parts:

| Part | Owns | Must not own |
|---|---|---|
| Settings | Per-community engagement policy, rate limits, quiet hours | Telegram network calls |
| Topics | Operator-defined topic triggers and reply guidance | Community relevance scoring |
| Memberships | Which managed account joined which community | Account health decisions beyond release outcome |
| Detection | Topic matching, reply drafting, candidate creation | Sending messages or joining groups |
| Review | Operator approval, rejection, and optional final text | Telethon sending |
| Send | Final preflight checks, public reply send, audit log | Candidate generation or topic scoring |

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

### Candidate Statuses

Allowed `engagement_candidates.status` values:

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
- A failed candidate may be re-approved by the operator when the failure was operational.
- The API must reject approval of expired candidates.

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
- No candidate is sent unless the candidate status is `approved`.
- No candidate is sent when `require_approval = false` in MVP because that setting is rejected.
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
| `suggest` | Draft candidate replies for operator review. |
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

Topic guidance should describe how to be useful, not how to manipulate the group.

Good guidance:

```text
Support thoughtful discussion of open-source CRM tools. Be factual, brief, and non-salesy.
Mention tradeoffs and practical evaluation criteria.
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

## Candidate Opportunities

Detection creates a candidate opportunity. Sending is a separate step.

Recommended table: `engagement_candidates`

```sql
id                       uuid PRIMARY KEY
community_id             uuid NOT NULL REFERENCES communities(id)
topic_id                 uuid NOT NULL REFERENCES engagement_topics(id)
source_tg_message_id     bigint
source_excerpt           text
detected_reason          text NOT NULL
suggested_reply          text
model                    text
model_output             jsonb
prompt_profile_id        uuid REFERENCES engagement_prompt_profiles(id)
prompt_profile_version_id uuid REFERENCES engagement_prompt_profile_versions(id)
prompt_render_summary    jsonb
risk_notes               text[] NOT NULL DEFAULT '{}'
status                   text NOT NULL DEFAULT 'needs_review'
                         -- needs_review | approved | rejected | sent | expired | failed
final_reply              text
reviewed_by              text
reviewed_at              timestamptz
expires_at               timestamptz NOT NULL
created_at               timestamptz NOT NULL DEFAULT now()
updated_at               timestamptz NOT NULL DEFAULT now()
```

Rules:

- Candidate rows must not include unnecessary Telegram user identity.
- `source_excerpt` must be capped and sanitized like analysis input message examples.
- Candidates expire quickly, usually within 24 hours.
- The same source message should not generate duplicate active candidates for the same topic.
- The suggested reply is a draft, not authorization to send.

Creation contract:

- `source_excerpt` maximum length is 500 characters.
- `suggested_reply` maximum length is 800 characters in MVP.
- `detected_reason` must be plain-language and operator-facing.
- `model_output` stores compact structured output, not full prompts or raw message batches.
- `prompt_render_summary` stores compact prompt provenance, not full raw prompt text.
- `risk_notes` stores model or rule-based caveats for operator review.
- `expires_at` defaults to 24 hours after creation.
- If raw message storage is disabled, the candidate may reference only source message IDs included
  in compact collection artifacts.

Deduplication contract:

- There may be only one active candidate for `(community_id, topic_id, source_tg_message_id)` where
  status is `needs_review` or `approved`.
- If `source_tg_message_id` is null, dedupe by `(community_id, topic_id, source_excerpt hash)` in
  service code.
- Expired, rejected, sent, and failed candidates do not block future candidates.

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

- Candidate must be `needs_review` or `failed`.
- Candidate must not be expired.
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
- `idempotency_key` for sends should be `engagement.send:{candidate_id}`.
- If a retry sees an existing `sent` action for the candidate, it must mark the candidate `sent` and
  skip network calls.
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

Detects relevant topic moments and creates candidate drafts.

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

- `engagement_candidates`

Rules:

- Do not send messages.
- An approved engagement target with `allow_detect = true` must exist for the community.
- Do not score or rank people.
- Prefer no candidate when topic fit is weak.
- Deduplicate active candidates by community, topic, and source message.
- Cap model input to compact samples and community-level context.

Worker preflight:

1. Load community.
2. Load settings; skip if mode is `disabled` or settings are missing.
3. Skip if mode is `observe` after writing optional debug logs only; no candidate is created in MVP.
4. Verify an approved engagement target with `allow_detect = true`.
5. Load active topics.
6. Load recent compact message samples.
7. Apply keyword prefilter.
8. Call OpenAI only for prefiltered topic/sample pairs.
9. Validate structured output.
10. Create candidate when `should_engage = true`.

Detection input contract:

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
  "messages": [
    {
      "tg_message_id": 123,
      "text": "truncated text",
      "message_date": "iso_datetime",
      "reply_context": "truncated parent text or null"
    }
  ],
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
- Maximum 20 messages per model call.
- Maximum 500 characters per message.
- Maximum serialized model input target: 64 KB.

Structured output contract:

```json
{
  "should_engage": true,
  "topic_match": "topic name",
  "source_tg_message_id": 123,
  "reason": "The group is discussing CRM alternatives.",
  "suggested_reply": "Short public reply text.",
  "risk_notes": []
}
```

### `engagement.send`

Sends one approved public reply.

Payload:

```json
{
  "candidate_id": "uuid",
  "approved_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="engagement_send")`

Rules:

- Candidate must be `approved`.
- Community settings must allow posting.
- An approved engagement target with `allow_post = true` must exist for the community.
- `require_approval` must be satisfied.
- The account must have joined the community.
- The joined membership account must be in the `engagement` account pool.
- Daily and spacing limits must pass for the account and community.
- MVP sends replies only; top-level posts are future/optional.
- Store an `engagement_actions` row whether the result is sent, failed, or skipped.

Worker preflight:

1. Load candidate with topic and community.
2. Skip if candidate is not approved.
3. Skip if candidate is expired.
4. Load settings; skip if missing, disabled, or `allow_post = false`.
5. Verify an approved engagement target with `allow_post = true`.
6. Reject top-level send if `reply_only = true` and `source_tg_message_id` is missing.
7. Load joined membership; skip if none exists.
8. Check community and account send limits.
9. Create or resume `engagement_actions` row with idempotency key.
10. Acquire the membership account with `purpose = engagement_send`.
11. Send reply through Telethon.
12. Mark action sent and candidate sent.
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

| Error | Account outcome | Action status | Candidate status |
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

System rules:

```text
You draft transparent, helpful public replies for an approved operator account.
Do not impersonate a normal community member.
Do not create urgency, deception, fake consensus, or claims of personal experience.
Do not target, profile, rank, or evaluate individual people.
Do not suggest direct messages.
Do not mention private/internal analysis.
Only produce a reply when it is genuinely useful and relevant.
Prefer no reply over a weak reply.
```

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

If `should_engage = false`, the worker should not create a candidate unless the operator requested a
debug trace.

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
- Candidate approval records the approving operator.
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

`EngagementCandidateOut`:

```json
{
  "id": "uuid",
  "community_id": "uuid",
  "community_title": "string|null",
  "topic_id": "uuid",
  "topic_name": "string",
  "source_tg_message_id": 123,
  "source_excerpt": "truncated text",
  "detected_reason": "plain-language reason",
  "suggested_reply": "draft reply",
  "final_reply": null,
  "risk_notes": [],
  "status": "needs_review",
  "reviewed_by": null,
  "reviewed_at": null,
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
/engagement_candidates
/approve_reply <candidate_id>
/reject_reply <candidate_id>
/join_community <community_id>
```

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
limits. If a candidate card would exceed Telegram limits, the bot should truncate the excerpt first,
then the detected reason, never the final reply text.

## Scheduling

Engagement detection can run after collection or on a separate low-frequency scheduler tick.

Recommended MVP:

- Only run detection for communities with engagement settings enabled.
- Run at most once per community per hour.
- Skip if there is already an active candidate for the same community/topic/source.
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
  "topic_id": "uuid|null",
  "status_message": "human readable short status",
  "started_at": "iso_datetime",
  "last_heartbeat_at": "iso_datetime"
}
```

Metrics or structured logs should count:

- candidates created
- candidates skipped by weak topic fit
- candidates skipped by dedupe
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
- candidate dedupe and expiration
- approve/reject transitions
- send preflight skips for missing settings, disabled settings, missing approval, expired candidate,
  no joined membership, and rate limits
- join worker success, already joined, inaccessible community, FloodWait, and banned account paths
- detect worker no-signal and candidate-created paths with fake LLM output
- send worker idempotency and no duplicate send on retry
- API auth and schema tests
- bot formatting/callback tests for candidate cards

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
