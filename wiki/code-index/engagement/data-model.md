# Engagement Data Model Map

## Scope

This shard covers the engagement database model and the migrations that define
the active task-first/cockpit schema.

## Source of truth

- `backend/db/models_engagement.py`
- `alembic/versions/20260419_0006_engagement_schema.py`
- `alembic/versions/20260419_0007_engagement_targets.py`
- `alembic/versions/20260420_0008_engagement_admin_control_plane.py`
- `alembic/versions/20260421_0010_engagement_embeddings.py`
- `alembic/versions/20260422_0012_engagement_candidate_timeliness.py`
- `alembic/versions/20260428_0013_task_first_engagements.py`
- `alembic/versions/20260428_0014_engagement_draft_update_requests.py`
- `alembic/versions/20260428_0015_engagement_target_duplicates.py`
- `alembic/versions/20260430_0016_engagement_opportunity_cadence.py`

## Functional groups

### Community-scoped settings and target intake

- `CommunityEngagementSettings`
  - older community-level posting mode, account, quiet-hours, and approval
    settings
- `EngagementTarget`
  - submitted target reference, approval/permission state, linked community,
    optional one-to-one engagement link

### First-class engagement setup

- `Engagement`
  - first-class engagement row keyed by target/community/topic/status
- `EngagementSettings`
  - per-engagement settings for mode, posting gates, quiet hours, and assigned
    account
- `EngagementDraftUpdateRequest`
  - edit-request lifecycle for replacement drafts in the approval queue
- `CommunityAccountMembership`
  - per-community membership state for engagement accounts

### Topic and semantic matching assets

- `EngagementTopic`
  - topic guidance, trigger keywords, negative keywords, good/bad reply examples
- `EngagementTopicEmbedding`
  - cached topic profile embeddings
- `EngagementMessageEmbedding`
  - cached message embeddings with TTL for semantic trigger selection

### Prompt and style control plane

- `EngagementPromptProfile`
  - active/inactive prompt profile metadata and current prompt text
- `EngagementPromptProfileVersion`
  - immutable prompt-profile history
- `EngagementStyleRule`
  - global/account/community/topic-scoped style rules with priority

### Candidate and action runtime state

- `EngagementCandidate`
  - detected opportunity, semantic/model evidence, deadlines, queue status,
    reply draft, and continuation/root classification
- `EngagementCandidateRevision`
  - manual edit history for a candidate reply
- `EngagementAction`
  - send/join/reply action history with idempotency and Telegram message IDs

## Migration roles

- `20260419_0006_engagement_schema.py`
  - base engagement schema
- `20260419_0007_engagement_targets.py`
  - target approval/permission gate
- `20260420_0008_engagement_admin_control_plane.py`
  - prompt profiles, versions, style rules, reply revision support
- `20260421_0010_engagement_embeddings.py`
  - semantic matching cache tables
- `20260422_0012_engagement_candidate_timeliness.py`
  - candidate review/reply deadline fields
- `20260428_0013_task_first_engagements.py`
  - first-class `engagements` and `engagement_settings` path
- `20260428_0014_engagement_draft_update_requests.py`
  - replacement-draft tracking table
- `20260428_0015_engagement_target_duplicates.py`
  - allows duplicate community reuse across different engagement targets
- `20260430_0016_engagement_opportunity_cadence.py`
  - root/continuation opportunity fields for send cadence

## Boundary notes

- The active operator model is `Engagement` plus `EngagementSettings`, not only
  `CommunityEngagementSettings`.
- Community-scoped tables are still live because compat services and worker
  lookups still depend on them.
- Candidate/action rows bridge backend, workers, and bot review surfaces.
