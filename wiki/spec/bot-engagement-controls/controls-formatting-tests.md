# Bot Engagement Controls Formatting And Tests

Inline control, formatting, and regression-test notes for the remaining
legacy/compat engagement bot surfaces.

## Inline Controls

The kept compat/manual layer is callback-first. The important live namespaces
here are:

```text
eng:admin:*
eng:set:*
eng:join:*
eng:detect:*
eng:actions:*
eng:t:*
eng:p:*
eng:style:*
eng:topic:*
eng:edit:save
eng:edit:cancel
```

Rules:

- Engagement callbacks stay inside the `eng:*` namespace.
- Settings, join, detect, and action-history controls must remain button-led;
  they should not depend on slash-command mirrors.
- Target, prompt, style, and topic controls may remain in compat/admin docs as
  long as they still match shipped code/tests.
- Exact callback tokens may evolve to preserve the Telegram 64-byte limit, but
  the namespace split should stay stable.

## Message Formatting

Compat/admin surfaces should still favor short operator-facing summaries before
 raw IDs.

Target cards should show:

- readiness
- status
- join/detect/post permission state
- submitted reference and resolved community when available
- last error when present
- audit IDs only in detail views

Send-safety cards should show:

- readiness
- posting posture
- pacing
- quiet hours when set
- assigned account when set
- button-led next actions instead of slash-command instructions

Prompt, style, and topic cards should keep:

- compact summaries first
- audit fields in detail views
- action buttons for edit/preview/activate/toggle flows

Action-history views should keep:

- compact audit list headers
- per-item cards with action type, state, timestamps, and capped outbound text
- paging controls under `eng:actions:*`

## Safety Rules

- Any control that can change posting behavior must show current state before
  mutation and resulting state after mutation.
- Assigned engagement account output must stay masked; never expose full phone
  numbers.
- Config-edit confirmation remains required for risky text/account mutations.
- The bot must not document or surface removed candidate-review command flows
  as if they are still live.

## Testing Contract

Keep regression coverage for:

- callback parsing for `eng:set:*`, `eng:join:*`, `eng:detect:*`,
  `eng:actions:*`, and `eng:admin:*`
- settings markup/buttons, including clear-quiet and clear-account callbacks
- handler flows for settings mutations, account confirmation, join/detect jobs,
  and action-history paging
- formatting regressions for target cards, send-safety cards, and action
  audit cards
- privacy regressions that ensure masked accounts and no phone-number leaks

## Open Questions

- Whether the remaining callback-first manual layer (`eng:set:*`,
  `eng:join:*`, `eng:detect:*`, `eng:actions:*`) is a long-term admin surface
  or only a temporary compat surface before deeper removal.
