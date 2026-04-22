# Bot Spec

Top-level routing contract for the Telegram operator UI. Command details live in `wiki/spec/bot/` shards.

## Responsibility

- Bot talks to the API only.
- Use Telegram-native command and inline callback surfaces for operator workflows.
- Keep discovery and engagement controls separated by callback namespace and permission boundary.

## Code Map

- `bot/main.py` - compatibility exports for legacy imports and `python -m bot.main` service entrypoint.
- `bot/app.py` - Telegram application wiring and handler registration.
- `bot/runtime*.py` - shared context, parsing, access, config-edit, markup, and reply helpers.
- `bot/account_handlers.py`, `bot/account_onboarding.py`, `bot/formatting_accounts.py` - bot-only
  Telegram account onboarding command preparation and safety copy.
- `bot/discovery_handlers.py` - discovery, seed, community, account, and upload handlers.
- `bot/callback_handlers.py` - inline callback router.
- `bot/engagement_commands_*.py` - engagement daily, admin, and config command handlers.
- `bot/engagement_*_flow.py` - engagement target, prompt/style, topic, and review workflow helpers.
- `bot/api_client.py` - backend API client.
- `bot/formatting_discovery.py` and `bot/formatting_engagement.py` - message formatting.
- `bot/ui_discovery.py` and `bot/ui_engagement.py` - inline controls.

## Shards

- [Discovery Commands](bot/discovery-commands.md)
- [Engagement Commands](bot/engagement-commands.md)
- [Access and UX](bot/access-ux.md)
