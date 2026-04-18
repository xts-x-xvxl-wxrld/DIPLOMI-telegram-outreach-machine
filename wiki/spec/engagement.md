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

## Non-Goals

- No direct messages to community members.
- No person-level persuasion scores, user rankings, or outreach priority lists.
- No covert identity behavior or fake organic consensus.
- No vote, reaction, subscriber, member, or view manipulation.
- No bulk joining or mass posting.
- No posting in communities that have not been explicitly approved for engagement.
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
status                   text NOT NULL DEFAULT 'needs_review'
                         -- needs_review | approved | rejected | sent | expired | failed
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
- The community must be approved for engagement.
- Private invite links are out of scope for MVP.
- Do not join multiple accounts unless requested by the operator.
- Respect FloodWait and account health mapping.

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

Writes:

- `engagement_candidates`

Rules:

- Do not send messages.
- Do not score or rank people.
- Prefer no candidate when topic fit is weak.
- Deduplicate active candidates by community, topic, and source message.
- Cap model input to compact samples and community-level context.

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
- `require_approval` must be satisfied.
- The account must have joined the community.
- Daily and spacing limits must pass for the account and community.
- MVP sends replies only; top-level posts are future/optional.
- Store an `engagement_actions` row whether the result is sent, failed, or skipped.

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

## Scheduling

Engagement detection can run after collection or on a separate low-frequency scheduler tick.

Recommended MVP:

- Only run detection for communities with engagement settings enabled.
- Run at most once per community per hour.
- Skip if there is already an active candidate for the same community/topic/source.
- Skip during quiet hours if configured.
- Do not enqueue sends automatically in MVP.

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
