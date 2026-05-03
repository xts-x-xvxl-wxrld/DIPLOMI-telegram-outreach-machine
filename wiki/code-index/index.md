# Code Index

Human-written code navigation maps for the live repo.

Start here before opening large code files.

## Maps

- [Engagement](engagement.md) - top-level engagement map across active,
  compatibility, and stale paths
- [Engagement Backend](engagement/backend.md) - API routers, service layers,
  queue seams, and backend ownership
- [Engagement Bot](engagement/bot.md) - callback ingress, task-first cockpit
  flows, compat/manual controls, and shared UI/formatting
- [Engagement Workers](engagement/workers.md) - scheduler, resolve, join,
  detect, send, and Telethon adapter seams
- [Engagement Data Model](engagement/data-model.md) - engagement tables,
  embeddings, candidates/actions, and migration anchors
- [Engagement Tests](engagement/tests.md) - test anchors grouped by API, bot,
  workers, schema, and compat coverage

## Rules

- Treat these maps as navigation, not behavior specs.
- Verify symbols with `rg` before editing.
- When docs and code disagree, active tests and code win.
