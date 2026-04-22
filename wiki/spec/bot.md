# Bot Spec

Top-level routing contract for the Telegram operator UI. Command details live in `wiki/spec/bot/` shards.

## Responsibility

- Bot talks to the API only.
- Use Telegram-native command and inline callback surfaces for operator workflows.
- Keep discovery and engagement controls separated by callback namespace and permission boundary.

## Code Map

- `bot/main.py` - command handlers and callback router.
- `bot/api_client.py` - backend API client.
- `bot/formatting_discovery.py` and `bot/formatting_engagement.py` - message formatting.
- `bot/ui_discovery.py` and `bot/ui_engagement.py` - inline controls.

## Shards

- [Discovery Commands](bot/discovery-commands.md)
- [Engagement Commands](bot/engagement-commands.md)
- [Access and UX](bot/access-ux.md)
