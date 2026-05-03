# Bot Operator Cockpit Spec

Top-level shell/context note for the inline operator cockpit. Details live in
`wiki/spec/bot-operator-cockpit/`.

## Responsibility

- Replace the old persistent reply keyboard with inline top-level navigation.
- Keep discovery, engagement, accounts, and help entrypoints visible and callback-routed.
- Maintain command compatibility while the cockpit becomes the preferred surface.

## Not The Source Of Truth

- This file does not define the active engagement UX contract.
- Engagement behavior under the inline cockpit is defined by
  `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`.
- Access/onboarding behavior is defined by `wiki/spec/bot/access-ux.md`.

## Shell Code Anchors

- `bot/main.py` - compatibility exports for legacy imports.
- `bot/app.py` - handler registration for cockpit commands and callbacks.
- `bot/callback_handlers.py` - callback dispatch for discovery and engagement cockpit actions.
- `bot/ui_discovery.py` and `bot/ui_engagement.py` - markup builders.
- `bot/formatting_discovery.py` and `bot/formatting_engagement.py` - cockpit cards.

## Remaining Shards

- [Navigation](bot-operator-cockpit/navigation.md)
- [Discovery Entry](bot-operator-cockpit/discovery-entry.md)
- [Entries and Rollout](bot-operator-cockpit/entries-rollout.md)
