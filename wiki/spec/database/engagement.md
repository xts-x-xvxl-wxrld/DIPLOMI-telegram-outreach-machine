# Database Engagement Tables

Engagement target, settings, prompt, style, candidate, and action schema contracts.

## Engagement Tables

The engagement module is optional and operator-controlled. These tables are present once the
engagement migrations are applied.

### `engagement_targets`

Manual allowlist for communities that may be used by the engagement module. Seed import, discovery,
expansion, collection, and community review do not create these rows.

```sql
id                    uuid PRIMARY KEY
community_id          uuid REFERENCES communities(id)
submitted_ref         text NOT NULL
submitted_ref_type    text NOT NULL DEFAULT 'telegram_username'
                      -- community_id | telegram_username | telegram_link | invite_link
status                text NOT NULL DEFAULT 'pending'
                      -- pending | resolved | approved | rejected | failed | archived
allow_join            boolean NOT NULL DEFAULT false
allow_detect          boolean NOT NULL DEFAULT false
allow_post            boolean NOT NULL DEFAULT false
notes                 text
added_by              text NOT NULL
approved_by           text
approved_at           timestamptz
last_error            text
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (community_id)
```

Worker gates:
- `community.join` requires an approved target with `allow_join = true`.
- `engagement.detect` requires an approved target with `allow_detect = true`.
- `engagement.send` requires an approved target with `allow_post = true`.

### `community_engagement_settings`

Per-community engagement controls. Absence of a row means engagement is disabled.

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

### `community_account_memberships`

Tracks which managed Telegram account has joined which community.

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

### `engagement_topics`

Operator-defined topics that can trigger a candidate public reply.

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

### `engagement_topic_embeddings`

Cached topic-profile embeddings used by semantic engagement matching.

```sql
id                    uuid PRIMARY KEY
topic_id              uuid NOT NULL REFERENCES engagement_topics(id)
model                 text NOT NULL
dimensions            int NOT NULL
profile_text_hash     text NOT NULL
embedding             jsonb NOT NULL
created_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (topic_id, model, dimensions, profile_text_hash)
```

### `engagement_message_embeddings`

Cached public-message embeddings used by semantic engagement matching.

```sql
id                    uuid PRIMARY KEY
community_id          uuid NOT NULL REFERENCES communities(id)
tg_message_id         bigint
source_text_hash      text NOT NULL
model                 text NOT NULL
dimensions            int NOT NULL
embedding             jsonb NOT NULL
expires_at            timestamptz NOT NULL
created_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (community_id, tg_message_id, source_text_hash, model, dimensions)
```

The first implementation keeps message embeddings in Postgres JSONB and validates dimensions in the
service layer before cache writes and reads. When `tg_message_id` is null, service logic still looks
up rows by `(community_id, source_text_hash, model, dimensions)` so semantic-only artifacts can
reuse recent cache entries even though the database uniqueness guard is weaker for null IDs.

### `engagement_prompt_profiles`

Admin-editable prompt profile state used by `engagement.detect`.

```sql
id                    uuid PRIMARY KEY
name                  text NOT NULL
description           text
active                boolean NOT NULL DEFAULT false
model                 text NOT NULL
temperature           numeric NOT NULL DEFAULT 0.2
max_output_tokens     int NOT NULL DEFAULT 1000
system_prompt         text NOT NULL
user_prompt_template  text NOT NULL
output_schema_name    text NOT NULL DEFAULT 'engagement_detection_v1'
created_by            text NOT NULL
updated_by            text NOT NULL
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()
```

Only one prompt profile should be active in the first implementation. Every profile mutation that
changes prompt/model fields creates an immutable version row.

### `engagement_prompt_profile_versions`

Immutable prompt profile history.

```sql
id                    uuid PRIMARY KEY
prompt_profile_id     uuid NOT NULL REFERENCES engagement_prompt_profiles(id)
version_number        int NOT NULL
model                 text NOT NULL
temperature           numeric NOT NULL
max_output_tokens     int NOT NULL
system_prompt         text NOT NULL
user_prompt_template  text NOT NULL
output_schema_name    text NOT NULL
created_by            text NOT NULL
created_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (prompt_profile_id, version_number)
```

### `engagement_style_rules`

Scoped admin voice and style rules assembled into engagement prompts.

```sql
id                    uuid PRIMARY KEY
scope_type            text NOT NULL DEFAULT 'global'
                      -- global | account | community | topic
scope_id              uuid
name                  text NOT NULL
rule_text             text NOT NULL
active                boolean NOT NULL DEFAULT true
priority              int NOT NULL DEFAULT 100
created_by            text NOT NULL
updated_by            text NOT NULL
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()
```

### `engagement_candidates`

Detected topic moments and suggested replies awaiting operator review.

```sql
id                       uuid PRIMARY KEY
community_id             uuid NOT NULL REFERENCES communities(id)
topic_id                 uuid NOT NULL REFERENCES engagement_topics(id)
source_tg_message_id     bigint
source_excerpt           text
source_message_date      timestamptz
detected_at              timestamptz NOT NULL
detected_reason          text NOT NULL
moment_strength          text NOT NULL
                         -- weak | good | strong
timeliness               text NOT NULL
                         -- fresh | aging | stale
reply_value              text NOT NULL
                         -- clarifying_question | practical_tip | correction | resource | other | none
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
review_deadline_at       timestamptz
reply_deadline_at        timestamptz NOT NULL
operator_notified_at     timestamptz
expires_at               timestamptz NOT NULL
created_at               timestamptz NOT NULL DEFAULT now()
updated_at               timestamptz NOT NULL DEFAULT now()
```

### `engagement_candidate_revisions`

Immutable edit history for candidate final replies.

```sql
id                    uuid PRIMARY KEY
candidate_id          uuid NOT NULL REFERENCES engagement_candidates(id)
revision_number       int NOT NULL
reply_text            text NOT NULL
edited_by             text NOT NULL
edit_reason           text
created_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (candidate_id, revision_number)
```

### `engagement_actions`

Audit log for joins, replies, sends, skips, and failures.

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

---
