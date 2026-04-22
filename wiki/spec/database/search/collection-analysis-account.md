# Database Collection Analysis And Account Tables

Detailed snapshot, collection, message, user, member, analysis, and account table contracts.

### `community_snapshots`
Point-in-time metadata snapshots for each monitored community. Discovery snapshots write these rows,
and engagement collection may also update them.

```sql
id                  uuid PRIMARY KEY
community_id        uuid REFERENCES communities(id)
member_count        int
message_count_7d    int                     -- messages in last 7 days at snapshot time
collected_at        timestamptz NOT NULL DEFAULT now()
```

---
### `collection_runs`
Durable run/artifact boundary shared by discovery snapshots, analysis collection, and engagement
collection.

`community.snapshot` writes one row per discovery snapshot attempt. Engagement collection writes one
row per message-intake attempt. Downstream jobs read this row by ID instead of receiving raw message
batches through Redis.

```sql
id                  uuid PRIMARY KEY
community_id        uuid REFERENCES communities(id)
brief_id            uuid REFERENCES audience_briefs(id)
status              text NOT NULL DEFAULT 'running'
                    -- 'running' | 'completed' | 'failed'
analysis_status     text NOT NULL DEFAULT 'pending'
                    -- 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'skipped'
window_days         int NOT NULL DEFAULT 90
window_start        timestamptz
window_end          timestamptz
messages_seen       int NOT NULL DEFAULT 0
members_seen        int NOT NULL DEFAULT 0
activity_events     int NOT NULL DEFAULT 0
snapshot_id         uuid REFERENCES community_snapshots(id)
analysis_input      jsonb
                    -- compact capped artifact or engagement batch, not full raw history
analysis_input_expires_at timestamptz
error_message       text
started_at          timestamptz NOT NULL DEFAULT now()
completed_at        timestamptz
```

`analysis_input` may include sampled/truncated message examples and aggregate signals, but it must stay compact:
- No full message history
- No phone numbers
- No person-level scores
- No unnecessary Telegram user identity
- Maximum 100 message examples
- Maximum 500 characters per message example
- Recommended maximum serialized size: 256 KB

---
### `messages`
Raw collected messages for engagement or future analysis collection. Only written when
`communities.store_messages = true`.
Default engagement collection pipeline: fetch -> count activity -> write compact collection artifact
or engagement batch -> enqueue detection -> expire the artifact later. No `messages` rows are written.

```sql
id                  uuid PRIMARY KEY
tg_message_id       bigint NOT NULL
community_id        uuid REFERENCES communities(id)
sender_user_id      bigint                  -- nullable (channels have no sender)
message_type        text                    -- 'text' | 'media_with_caption' | 'forward' | 'poll' | 'other'
text                text
has_forward         boolean DEFAULT false
forward_from_id     bigint                  -- tg_id of source channel/chat if forwarded
reply_to_message_id bigint
views               int
reactions_count     int
collected_at        timestamptz NOT NULL DEFAULT now()
message_date        timestamptz NOT NULL

UNIQUE (community_id, tg_message_id)
```

When `store_messages = false` (default):
- Messages are fetched in memory during the collection run
- Activity counts are tallied per user and written to `community_members`
- A compact, capped analysis artifact is written to `collection_runs.analysis_input`
- The analysis worker receives only `collection_run_id`
- Raw messages are discarded by the collection worker

When `store_messages = true` (opt-in, per community):
- All of the above, plus rows are written to this table
- Enables re-analysis, export, and audit

---
### `users`
Central registry of all Telegram users seen across any monitored community.
One row per unique Telegram user. Identity fields stored once here, not repeated per community.
Authorized research use only. Phone is never stored.

```sql
id                  uuid PRIMARY KEY
tg_user_id          bigint UNIQUE NOT NULL
username            text                    -- nullable, depends on user privacy settings
first_name          text                    -- nullable
first_seen_at       timestamptz NOT NULL DEFAULT now()
last_updated_at     timestamptz NOT NULL DEFAULT now()
```

Use `SELECT community_id FROM community_members WHERE user_id = <id>` to look up all
communities a user belongs to.

---
### `community_members`
One row per (community, user) pair. Tracks membership and activity only.
Identity fields live in `users`, not here.

```sql
id                  uuid PRIMARY KEY
community_id        uuid REFERENCES communities(id)
user_id             uuid REFERENCES users(id)
activity_status     text NOT NULL DEFAULT 'inactive'
                    -- 'inactive' (0 events) | 'passive' (1-4) | 'active' (5+)
event_count         int NOT NULL DEFAULT 0  -- activity events in rolling 90-day window
last_active_at      timestamptz             -- timestamp of most recent activity event
first_seen_at       timestamptz NOT NULL DEFAULT now()
last_updated_at     timestamptz NOT NULL DEFAULT now()

UNIQUE (community_id, user_id)
```

**Activity events counted (rolling 90-day window):**
- Messages posted in the community
- Forwards into the community (message with fwd_from)
- Other attributable service events (polls, pins)

Activity status is recalculated on every collection run:
- 0 events â†’ `inactive`
- 1-4 events â†’ `passive`
- 5+ events â†’ `active`

---
### `analysis_summaries`
LLM-generated community summaries. One row per community per analysis run.

```sql
id                  uuid PRIMARY KEY
community_id        uuid REFERENCES communities(id)
brief_id            uuid REFERENCES audience_briefs(id)
summary             text                    -- plain-language community description
dominant_themes     text[]
activity_level      text                    -- 'low' | 'moderate' | 'high'
is_broadcast        boolean                 -- true = channel, false = discussion group
relevance_score     numeric(3,2)            -- 0.00 to 1.00
relevance_notes     text                    -- why this score was assigned
centrality          text                    -- 'core' | 'peripheral'
analysis_window_days int DEFAULT 90
analyzed_at         timestamptz NOT NULL DEFAULT now()
model               text                    -- e.g. 'gpt-4o'
```

---
### `telegram_accounts`
Managed Telegram accounts used by Telethon workers.

```sql
id                  uuid PRIMARY KEY
phone               text UNIQUE NOT NULL
session_file_path   text NOT NULL           -- path inside /sessions volume
account_pool        text NOT NULL DEFAULT 'search'
                    -- 'search' | 'engagement' | 'disabled'
status              text NOT NULL DEFAULT 'available'
                    -- 'available' | 'in_use' | 'rate_limited' | 'banned'
flood_wait_until    timestamptz             -- set when rate_limited
lease_owner         text                    -- RQ job id that currently owns the lease
lease_expires_at    timestamptz             -- stale in_use leases may be recovered after this
last_used_at        timestamptz
added_at            timestamptz NOT NULL DEFAULT now()
last_error          text
notes               text
```

`account_pool` separates read-only search identities from public engagement identities. Existing
accounts should default to `search` when the column is introduced; accounts must be explicitly marked
`engagement` before they can join communities or send public replies.

---
