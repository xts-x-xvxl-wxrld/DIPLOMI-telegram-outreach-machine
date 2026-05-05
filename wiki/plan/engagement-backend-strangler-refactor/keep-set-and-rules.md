# Engagement Backend Strangler — Active Keep-Set and Refactor Rules

## Active Keep-Set

Treat these as the contract-bearing backend modules during the refactor:

- `backend/api/routes/engagement_task_first.py`
- `backend/api/routes/engagement_cockpit.py`
- `backend/services/task_first_engagements.py`
- `backend/services/task_first_engagement_cockpit.py`
- `backend/services/task_first_engagement_cockpit_mutations.py`
- `backend/services/task_first_engagement_issues.py`
- `backend/queue/payloads.py`
- `backend/queue/client.py`
- `backend/workers/community_join.py`
- `backend/workers/engagement_detect*.py`
- `backend/workers/engagement_scheduler.py`
- `backend/workers/engagement_send.py`
- `backend/db/models_engagement.py`

Treat these as compat-only unless a phase explicitly extracts shared
primitives from them:

- `backend/api/routes/engagement.py`
- `backend/api/routes/engagement_targets.py`
- `backend/api/routes/engagement_settings_topics.py`
- `backend/api/routes/engagement_prompts_style.py`
- `backend/api/routes/engagement_candidates_actions.py`
- `backend/services/community_engagement.py`
- `backend/services/community_engagement_*.py`

## Refactor Rules

1. Do not add new active behavior through compat routers or compat export
   facades.
2. Preserve queue payload shapes and deterministic job IDs until an explicit
   migration plan says otherwise.
3. Preserve current bot-visible semantics while moving ownership.
4. Prefer extracting shared primitives over duplicating logic across active and
   compat paths.
5. Do not prune compat modules until active workers and active routes no
   longer depend on them.
