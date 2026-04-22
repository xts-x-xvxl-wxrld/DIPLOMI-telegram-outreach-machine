# Database Search Core Tables

Detailed query-driven search run, query, candidate, evidence, and review table contracts.

### `search_runs`

One operator query-driven search intent.

```sql
id                    uuid PRIMARY KEY
raw_query             text NOT NULL
normalized_title      text NOT NULL
requested_by          text
status                text NOT NULL DEFAULT 'draft'
                      -- draft | planning | retrieving | ranking | completed | failed | cancelled
enabled_adapters      text[] NOT NULL DEFAULT '{telegram_entity_search}'
language_hints        text[] NOT NULL DEFAULT '{}'
locale_hints          text[] NOT NULL DEFAULT '{}'
per_run_candidate_cap int NOT NULL DEFAULT 100
per_adapter_caps      jsonb NOT NULL DEFAULT '{}'
planner_source        text
planner_metadata      jsonb NOT NULL DEFAULT '{}'
ranking_version       text
ranking_metadata      jsonb NOT NULL DEFAULT '{}'
last_error            text
started_at            timestamptz
completed_at          timestamptz
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()
```

Rules:
- `raw_query` preserves the operator input.
- `normalized_title` is a short display title derived from the query.
- `enabled_adapters` initially supports `telegram_entity_search` only.
- `per_adapter_caps` may override defaults such as `{"telegram_entity_search": {"per_query": 25}}`.
- `last_error` is populated when status becomes `failed`.
### `search_queries`

Generated subqueries for one run and one retrieval adapter.

```sql
id                    uuid PRIMARY KEY
search_run_id         uuid NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE
adapter               text NOT NULL
query_text            text NOT NULL
normalized_query_key  text NOT NULL
language_hint         text
locale_hint           text
include_terms         text[] NOT NULL DEFAULT '{}'
exclusion_terms       text[] NOT NULL DEFAULT '{}'
status                text NOT NULL DEFAULT 'pending'
                      -- pending | running | completed | failed | skipped
planner_source        text NOT NULL DEFAULT 'deterministic_v1'
planner_metadata      jsonb NOT NULL DEFAULT '{}'
error_message         text
started_at            timestamptz
completed_at          timestamptz
created_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (search_run_id, adapter, normalized_query_key)
```

`normalized_query_key` is the case-folded, whitespace-normalized query text used for idempotent
planner writes.
### `search_candidates`

Run-scoped candidate communities discovered by search.

```sql
id                    uuid PRIMARY KEY
search_run_id         uuid NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE
community_id          uuid REFERENCES communities(id)
status                text NOT NULL DEFAULT 'candidate'
                      -- candidate | promoted | rejected | archived | converted_to_seed
normalized_username   text
canonical_url         text
raw_title             text
raw_description       text
raw_member_count      int
adapter_first_seen    text
score                 numeric(8,3)
score_components      jsonb NOT NULL DEFAULT '{}'
ranking_version       text
first_seen_at         timestamptz NOT NULL DEFAULT now()
last_seen_at          timestamptz NOT NULL DEFAULT now()
reviewed_at           timestamptz
last_reviewed_by      text
```

Uniqueness rules:
- one candidate per `(search_run_id, community_id)` when `community_id IS NOT NULL`
- one candidate per `(search_run_id, normalized_username)` when `normalized_username IS NOT NULL`
- one candidate per `(search_run_id, canonical_url)` when `canonical_url IS NOT NULL`

Application merge order is `community_id`, then `normalized_username`, then `canonical_url`.
Unresolved candidates are allowed, but retrieval must fill at least one of `community_id`,
`normalized_username`, or `canonical_url`.
### `search_candidate_evidence`

Compact evidence explaining why a candidate matched.

```sql
id                    uuid PRIMARY KEY
search_run_id         uuid NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE
search_candidate_id   uuid NOT NULL REFERENCES search_candidates(id) ON DELETE CASCADE
community_id          uuid REFERENCES communities(id)
search_query_id       uuid REFERENCES search_queries(id) ON DELETE SET NULL
adapter               text NOT NULL
query_text            text
evidence_type         text NOT NULL
                      -- entity_title_match | entity_username_match | description_match
                      -- handle_resolution | manual_seed | linked_discussion | forward_source
                      -- telegram_link | mention | post_text_match | web_result
evidence_value        text
evidence_metadata     jsonb NOT NULL DEFAULT '{}'
source_community_id   uuid REFERENCES communities(id)
source_seed_group_id  uuid REFERENCES seed_groups(id)
source_seed_channel_id uuid REFERENCES seed_channels(id)
captured_at           timestamptz NOT NULL DEFAULT now()
```

Rules:
- First active evidence types are `entity_title_match`, `entity_username_match`,
  `description_match`, `handle_resolution`, `manual_seed`, `linked_discussion`, `forward_source`,
  `telegram_link`, and `mention`.
- `post_text_match` and `web_result` are reserved until their adapters are enabled.
- `evidence_value` must be truncated to 500 characters before persistence.
- `evidence_metadata` should stay compact, with an application-enforced target cap of 8 KB.
- Evidence rows must not store sender identity, phone numbers, full raw message history, or
  person-level scores.
### `search_reviews`

Operator review audit rows for search candidates.

```sql
id                    uuid PRIMARY KEY
search_run_id         uuid NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE
search_candidate_id   uuid NOT NULL REFERENCES search_candidates(id) ON DELETE CASCADE
community_id          uuid REFERENCES communities(id)
action                text NOT NULL
                      -- promote | reject | archive | global_reject | convert_to_seed
scope                 text NOT NULL DEFAULT 'run'
                      -- run | global
requested_by          text
notes                 text
metadata              jsonb NOT NULL DEFAULT '{}'
created_at            timestamptz NOT NULL DEFAULT now()
```

Rules:
- `promote`, `reject`, and `archive` are run-scoped by default.
- `global_reject` is the only first-class search action allowed to mutate global community
  rejection state.
- `convert_to_seed` requires a resolved `community_id` or public username/canonical URL and is
  enabled in a later slice.
- Review rows are append-only audit facts; `search_candidates.status` stores the current run-scoped
  review state.

---
