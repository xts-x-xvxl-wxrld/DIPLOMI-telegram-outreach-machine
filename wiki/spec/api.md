# API Spec

Top-level routing contract for the FastAPI surface. Endpoint details live in `wiki/spec/api/` shards.

## Responsibility

- Expose bot-facing REST endpoints with bearer-token auth.
- Keep request handlers thin and route behavior to services/workers.
- Preserve community-level privacy boundaries and avoid OpenAI calls in API handlers.

## Code Map

- `backend/api/routes/search.py` - search run create/list/detail, query/candidate listing, rerank job, and review routes.
- `backend/api/routes/seeds.py` - seed, community, snapshot, and debug routes.
- `backend/api/routes/engagement.py` - engagement compatibility router.
- `backend/api/routes/engagement_*.py` - engagement target, settings/topic, prompt/style, and candidate/action resources.
- `backend/api/routes/accounts.py` - bot-driven Telegram account onboarding start/complete routes.
- `backend/api/routes/telegram_entities.py` - direct handle intake routes.
- `backend/api/schemas.py` - shared response schemas.

## Shards

- [Foundation](api/foundation.md)
- [Briefs and Search](api/briefs-search.md)
- [Discovery](api/discovery.md)
- [Communities, Snapshots, Analysis](api/communities-snapshots.md)
- [Engagement](api/engagement.md)
- [Accounts](api/accounts.md)
- [Jobs and Debug](api/jobs-debug.md)
