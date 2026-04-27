# Bot Cockpit Simplification

Screen-level UX simplifications to reduce noise and friction across the operator cockpit.
Companion to `wiki/spec/bot-operator-cockpit-v2.md`, which covers top-level navigation.

## Motivation

The v2 cockpit redesign promotes daily actions to the home screen. This spec addresses
the remaining friction inside each screen: over-verbose cards, redundant navigation
steps, internal state exposed as operator UI, and settings knobs that the wizard
already handles.

## Goals

- Reduce the candidate review card to what an operator needs to decide: approve or reject.
- Remove the redundant `Open` detour from the candidate review flow.
- Remove status filter tabs that are not part of the daily operator path.
- Strip per-action permission toggles from the settings screen.
- Remove the dead-end Limits screen.
- Remove the redundant `Add target` button from the community list.
- Keep all slash commands and item-level callbacks intact.

## Non-Goals

- No changes to wizard step logic or contracts.
- No changes to backend API routes or data models.
- No removal of audit or diagnostic data — move it to detail views, not away entirely.
- No changes to the discovery cockpit.

---

## 1. Candidate Review Card

### Problem

`format_engagement_candidate_card` in `bot/formatting_engagement_review.py` shows:

- Readiness label and Status (redundant with each other)
- Timeliness, moment strength, reply value scores
- Review and reply deadlines
- Source excerpt (up to 500 chars)
- Detected reason (up to 260 chars)
- Suggested reply (up to 800 chars)
- Final reply if edited
- Prompt profile version
- Risk notes
- "Reply opportunity ID" and "Candidate ID" as two separate fields (same value)
- A full block of slash commands as plain text

On mobile, this card is overwhelming. The operator needs to answer one question:
is this reply worth sending?

### Target card shape

```text
<Community> · <Topic>

Source:
<source excerpt — max 300 chars>

Draft reply:
<suggested reply — max 600 chars>

<Edited reply if different from draft>

<Risk notes if present — max 120 chars>

Candidate ID: <id>
```

Rules:

- Drop the `Status` field. Readiness is sufficient and uses plain language.
- Drop timeliness, moment strength, and reply value from the card. Move to detail view.
- Drop deadlines from the card. Move to detail view.
- Drop prompt profile version from the card. Move to detail view.
- Show risk notes only when present; cap at 120 chars with a truncation indicator.
- Show candidate ID once, at the bottom, for traceability.
- Remove the slash command block entirely. Buttons are the action surface.

### Detail view

`ACTION_ENGAGEMENT_CANDIDATE_OPEN` remains and opens a detail view. The detail view
shows the full card plus the fields stripped from the list card:

- Timeliness, moment strength, reply value
- Review and reply deadlines
- Prompt profile name and version
- Full risk notes

The detail view does not duplicate the action buttons already on the list card.

---

## 2. Remove the "Open" Detour from the Review Flow

### Problem

The candidate list shows each card with full content and action buttons
(`✏ Edit`, `✅ Approve`, `✖ Reject`), and also a `👀 Open` button that leads to a
separate detail view with the same content and the same action buttons. This is one
unnecessary tap with no new information for the common case.

### Target flow

```text
Review list
  card + [Edit]  [Approve]  [Reject]
  card + [Edit]  [Approve]  [Reject]
  ...
  [← Prev]  [Next →]
```

Remove `👀 Open` from `engagement_candidate_actions_markup`.

`ACTION_ENGAGEMENT_CANDIDATE_OPEN` remains routable via callback and slash command for
the detail view. It is removed from the primary list buttons only.

---

## 3. Candidate Status Filter Tabs

### Problem

Every candidate list screen (`engagement_candidate_filter_markup`) renders five tab
buttons: `Needs Review`, `Approved`, `Failed`, `Sent`, `Rejected`. These appear on
every page of the list, consuming two rows of button space on every screen.

`Sent` and `Rejected` are archive states, not daily work. `Failed` belongs to the
"Needs attention" path surfaced on the home dashboard.

### Target behavior

Show two primary tabs inline on the list header:

```text
[• Needs review]  [Approved]
```

Move `Failed`, `Sent`, and `Rejected` behind a `▾ More` button or to the detail view
of the relevant candidate. The home dashboard already routes the operator to the right
tab directly, so the tabs exist for navigation within the list, not for discovery.

---

## 4. Settings Screen — Strip Per-Action Permission Toggles

### Problem

`engagement_settings_markup` in `bot/ui_engagement.py` shows ten controls:

- Mode presets: Off / Observe / Suggest / Ready
- `Join on/off`, `Post on/off` per-action toggles
- Max/day, Edit gap, Quiet start, Quiet end
- Assign account

The `Join on/off` and `Post on/off` toggles duplicate what the wizard derives from
the Level choice. An operator who used the wizard should never need to touch these.
Showing them as editable buttons exposes the internal permission flag model and invites
misconfiguration (e.g. setting mode to Sending but leaving `Post on` as off).

### Target button set

```text
[⏸ Off]  [👀 Observe]  [✍ Suggest]  [📤 Send]

[📏 Max/day]  [⏱ Gap]
[🌙 Quiet start]  [🌅 Quiet end]
[📲 Account]

[🤝 Queue join]  [🔎 Detect now]
```

Rules:

- Remove `Join on/off` and `Post on/off` buttons.
- Keep the four mode presets as the primary engagement state control.
- Keep cadence and quiet hours.
- Keep account assignment.
- Keep `Queue join` and `Detect now` as operational triggers.

The per-action flags remain writable via slash command and the advanced/admin path for
operators who need to override wizard-derived values.

---

## 5. Remove the Dead-End Limits Screen

### Problem

`format_engagement_admin_limits_home` renders a screen that says: "Open a community
first, then tune its posting limits, quiet hours, and engagement account." It has no
action buttons relevant to the operator's current position.

In the v2 Manage screen, `Accounts` routes directly to account pool health
(`op:accounts`) and `Communities` routes directly to the community list
(`eng:targets 0`). There is no remaining reason for the Limits screen to exist as a
separate destination.

### Target behavior

Remove `ACTION_ENGAGEMENT_ADMIN_LIMITS` from `engagement_admin_home_markup`.
Remove `format_engagement_admin_limits_home` from `bot/formatting_engagement.py`.

If the Settings Lookup list (community list filtered to approved communities with
settings) is needed as a standalone view, it remains accessible via
`/engagement_settings` with no community ID argument, and via `op:manage → Communities`.

---

## 6. Remove Redundant "Add Target" from Community List

### Problem

`engagement_target_list_markup` places `➕ Add target` as the first button on the
community list. With the wizard promoted to the home dashboard in v2, this button is
redundant. Operators who want to add a community use `➕ Add community` on the home
screen.

### Target behavior

Remove `➕ Add target` from `engagement_target_list_markup`.

`/add_engagement_target` and `op:add` remain as the wizard entry points.

---

## 7. Community List — Simplify Status Filters

### Problem

`engagement_target_list_markup` inherits `_target_status_filter_rows` which renders
filter buttons exposing internal status machine states: `pending`, `resolved`,
`approved`, `rejected`, `archived`. These map to the six-state approval machine in
`engagement_targets.status`, which the wizard is supposed to hide from operators.

Most operators only care about `approved` communities (the ones actively engaging).
`pending` and `resolved` are transitional wizard states. `rejected` and `archived` are
historical.

### Target behavior

Default the community list to approved targets with no visible filter. Add a single
`▾ All statuses` toggle for operators who need to debug the pipeline.

The internal status field remains on community detail cards for traceability, but is
not the primary navigation axis.

---

## Implementation And Rollout

The implementation details for the community target card, code map, testing contract,
and rollout order now live in
`wiki/spec/bot-cockpit-simplification/implementation-and-rollout.md`.
