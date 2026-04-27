# Bot Cockpit Experience: Attention And Navigation

Compatibility note:

`wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md` is the only
active source of truth for home behavior, top-level issue surfacing, and footer
navigation.

This shard must not redefine:

- the `Engagements` home state model
- `Top issues` as the top-level issue surface
- `Back` plus `<< Engagements` navigation outside the wizard
- wizard-only `Back` navigation inside the wizard
- any `Home` button model from the older cockpit

The older combined `Needs attention` contract and `Home` footer contract are
superseded and should not be implemented.

Until this shard is rewritten, use it only for low-level implementation notes
that do not conflict with the task-first cockpit spec.
