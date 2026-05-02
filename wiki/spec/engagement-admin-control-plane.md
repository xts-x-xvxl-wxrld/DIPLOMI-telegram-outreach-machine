# Engagement Admin Control Plane Spec

Top-level routing contract for manual engagement target, prompt, topic, style, and reply administration. Details live in `wiki/spec/engagement-admin-control-plane/`.

## Responsibility

- Separate daily engagement review from admin configuration.
- Require explicit permission gates for target resolution, joining, detection, and posting.
- Keep prompt/style/reply changes auditable and reversible.

## Code Map

- `backend/api/routes/engagement.py` - admin API compatibility router.
- `backend/api/routes/engagement_*.py` - admin target, topic, prompt, style, candidate, and action resources.
- `backend/services/community_engagement.py` - compatibility exports for admin services.
- `backend/services/community_engagement_*.py` - admin persistence and validation by engagement subdomain.
- `bot/config_editing.py` - edit registry.
- `bot/formatting_engagement.py` and `bot/ui_engagement.py` - admin bot surfaces.

## Shards

- [Targets and Prompts](engagement-admin-control-plane/targets-prompts.md)
- [Topics, Style, Replies](engagement-admin-control-plane/topics-style-replies.md)
- [Draft Instruction Wizard](engagement-admin-control-plane/draft-instruction-wizard.md)
- [Surfaces and Tests](engagement-admin-control-plane/surfaces-tests.md)
