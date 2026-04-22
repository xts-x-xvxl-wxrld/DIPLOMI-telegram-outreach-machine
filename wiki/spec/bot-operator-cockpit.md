# Bot Operator Cockpit Spec

Top-level routing contract for the inline operator cockpit. Details live in `wiki/spec/bot-operator-cockpit/`.

## Responsibility

- Replace the old persistent reply keyboard with inline top-level navigation.
- Keep discovery, engagement, accounts, and help entrypoints visible and callback-routed.
- Maintain command compatibility while the cockpit becomes the preferred surface.

## Code Map

- `bot/main.py` - cockpit commands and callback dispatch.
- `bot/ui_discovery.py` and `bot/ui_engagement.py` - markup builders.
- `bot/formatting_discovery.py` and `bot/formatting_engagement.py` - cockpit cards.

## Shards

- [Navigation](bot-operator-cockpit/navigation.md)
- [Discovery Entry](bot-operator-cockpit/discovery-entry.md)
- [Entries and Rollout](bot-operator-cockpit/entries-rollout.md)
