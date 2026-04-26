# Engagement Add Wizard Permission Collapse

Inventory of redundant or MVP-locked engagement controls hidden, derived, or removed by the
wizard described in `wiki/plan/engagement-add-wizard/overview.md`. Cockpit settings continue to
expose what remains after collapse.

## Removed (MVP-locked, single-valued)

- `community_engagement_settings.reply_only` — locked to `true` in
  `backend/services/community_engagement_settings.py:325-329`. Drop from the API request schema and
  from the settings update path. Hardcode the consumer-side check in the worker until the MVP
  constraint is lifted.
- `community_engagement_settings.require_approval` — locked to `true` in
  `community_engagement_settings.py:320-324`. Same treatment as above.

## Derived (no longer operator-facing)

- `engagement_targets.allow_join` — always `true` once Step 3 succeeds. The account's chat
  membership is the real join state; this flag is redundant. Drop the per-Level mapping and stop
  toggling it from the wizard.
- `engagement_targets.allow_detect`, `allow_post` — derived from the wizard's Level choice.
  Mapping:
  - Watching → `allow_detect=true`, `allow_post=false`.
  - Suggesting → `allow_detect=true`, `allow_post=false` (reply queueing applied in the worker).
  - Sending → `allow_detect=true`, `allow_post=true`.
- `engagement_targets.status` — operator never sees the six-state machine. The wizard transitions
  it implicitly: `RESOLVED` after Step 1, `APPROVED` after Step 5. Other states remain valid for
  backend workflow but are not presented in the wizard.
- `community_engagement_settings.allow_join` and `allow_post` — same Level-derived mapping. The
  defensive double-check today in `engagement_detect_process.py:48-51` and
  `engagement_send.py:119-125` becomes redundant once `mode` is the single operator-facing source
  of truth.

## Hidden (kept in cockpit, not in the wizard)

- Cadence: `max_posts_per_day`, `min_minutes_between_posts`. Live in the cockpit settings tab,
  with current preset defaults preserved.
- Quiet hours: `quiet_hours_start`, `quiet_hours_end`. Cockpit settings tab.
- Voice and style rules at any scope. Cockpit "Library" area.
- Prompt profiles. Cockpit "Library" area.
- Per-target raw status transitions and per-action permission toggles. Available only to admin
  surfaces, not the operator wizard.

## Kept as-is

- The `EngagementMode` enum values themselves remain in the database as the canonical truth. The
  wizard's Level → mode mapping is documented in
  `wiki/plan/engagement-add-wizard/steps.md`.
- `AccountPool` separation. Step 3 of the wizard filters to ENGAGEMENT pool accounts only.
- `EngagementTopic.active`. The wizard forces `active=true` on any topic it attaches; deactivation
  remains a cockpit action.

## Migration Notes

- Removing the locked flags can be staged:
  1. First, drop the flags from the API request schema and from the operator-facing settings UI.
     Keep the columns and have writes hardcode `true`.
  2. After one release with no rollback hits, drop the columns in an Alembic migration.
- Existing communities at `mode = DISABLED` continue to work. The wizard never produces
  `DISABLED`; an operator can still flip a community to off via the cockpit settings.
- The Level → mode mapping must match the existing preset table in
  `wiki/plan/engagement-operator-controls/surface.md` so cockpit and wizard agree.

## Validation Hooks

- A unit or service test asserting that `community_engagement_settings.create` and `update` paths
  reject any attempt to set `require_approval=False` or `reply_only=False` while the MVP
  constraint stands.
- A wizard test asserting that each Level selection produces the documented engagement mode and
  the documented derived per-action flags on both the target and the settings rows.
- A service test asserting that re-entering the wizard for a partially-configured community does
  not duplicate target rows, topic attachments, or account memberships.
