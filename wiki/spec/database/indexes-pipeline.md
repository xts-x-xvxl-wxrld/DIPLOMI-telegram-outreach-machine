# Database Indexes And Collection Pipeline

Minimum index and default collection pipeline contracts.

## Indexes (minimum set)

```sql
CREATE INDEX ON communities (status);
CREATE INDEX ON communities (brief_id);
CREATE INDEX ON communities (store_messages);
CREATE INDEX ON collection_runs (community_id, started_at DESC);
CREATE INDEX ON collection_runs (analysis_status);
CREATE INDEX ON collection_runs (analysis_input_expires_at);
CREATE INDEX ON messages (community_id, message_date);   -- only relevant when store_messages = true
CREATE INDEX ON users (tg_user_id);
CREATE INDEX ON community_members (community_id, activity_status);
CREATE INDEX ON community_members (user_id);
CREATE INDEX ON analysis_summaries (community_id, analyzed_at DESC);
CREATE INDEX ON telegram_accounts (status);
CREATE INDEX ON telegram_accounts (account_pool, status, last_used_at);
CREATE INDEX ON telegram_accounts (lease_expires_at);
CREATE INDEX ON community_discovery_edges (seed_group_id);
CREATE INDEX ON community_discovery_edges (seed_channel_id);
CREATE INDEX ON community_discovery_edges (source_community_id);
CREATE INDEX ON community_discovery_edges (target_community_id);
CREATE INDEX ON telegram_entity_intakes (status);
CREATE INDEX ON telegram_entity_intakes (entity_type);
CREATE INDEX ON telegram_entity_intakes (community_id);
CREATE INDEX ON telegram_entity_intakes (user_id);
CREATE INDEX ON search_runs (status, created_at DESC);
CREATE INDEX ON search_runs (requested_by, created_at DESC);
CREATE INDEX ON search_queries (search_run_id, status);
CREATE INDEX ON search_queries (adapter, status);
CREATE INDEX ON search_candidates (search_run_id, status);
CREATE INDEX ON search_candidates (community_id);
CREATE INDEX ON search_candidates (score DESC);
CREATE UNIQUE INDEX ON search_candidates (search_run_id, community_id)
  WHERE community_id IS NOT NULL;
CREATE UNIQUE INDEX ON search_candidates (search_run_id, normalized_username)
  WHERE normalized_username IS NOT NULL;
CREATE UNIQUE INDEX ON search_candidates (search_run_id, canonical_url)
  WHERE canonical_url IS NOT NULL;
CREATE INDEX ON search_candidate_evidence (search_candidate_id, captured_at);
CREATE INDEX ON search_candidate_evidence (search_run_id, evidence_type);
CREATE INDEX ON search_candidate_evidence (community_id);
CREATE INDEX ON search_reviews (search_candidate_id, created_at DESC);
CREATE INDEX ON search_reviews (search_run_id, action);
```

Engagement indexes:

```sql
CREATE INDEX ON engagement_targets (community_id);
CREATE INDEX ON engagement_targets (status);
CREATE INDEX ON engagement_targets (submitted_ref);
CREATE INDEX ON community_engagement_settings (community_id);
CREATE INDEX ON community_account_memberships (community_id, telegram_account_id);
CREATE INDEX ON engagement_topics (active);
CREATE INDEX ON engagement_topic_embeddings (topic_id);
CREATE INDEX ON engagement_message_embeddings (community_id, source_text_hash, model, dimensions);
CREATE INDEX ON engagement_message_embeddings (expires_at);
CREATE INDEX ON engagement_candidates (status, created_at);
CREATE INDEX ON engagement_candidates (community_id, topic_id, status);
CREATE INDEX ON engagement_actions (community_id, created_at);
CREATE INDEX ON engagement_actions (telegram_account_id, created_at);
CREATE INDEX ON engagement_prompt_profiles (active);
CREATE INDEX ON engagement_prompt_profile_versions (prompt_profile_id);
CREATE INDEX ON engagement_style_rules (scope_type, scope_id, active, priority);
CREATE INDEX ON engagement_candidate_revisions (candidate_id, revision_number);
```

---
## Default Engagement Collection Pipeline (store_messages = false)

```
engagement collection worker
  -> fetch recent messages from Telegram (in memory)
  -> tally activity events per user_id (in memory)
  -> write/update community_members rows
  -> write community_snapshots row
  -> write collection_runs row with compact artifact or engagement batch
  -> enqueue engagement.detect with collection_run_id when eligible
  -> discard raw messages

engagement.detect worker
  -> read collection_runs artifact or stored messages
  -> apply topic/timing/policy gates
  -> call OpenAI only for selected trigger posts
  -> create reply opportunities when useful
```

No rows are written to `messages` or `message_reactions` in this path. The temporary `collection_runs.analysis_input` expires after the retention window defined in the queue spec.

---
## Open Questions

- Retention policy for opt-in stored messages (rolling 180-day window with pruning job)?
- Should `community_members` track which specific event types contributed to `event_count` (separate counters for messages vs reactions vs forwards)?
