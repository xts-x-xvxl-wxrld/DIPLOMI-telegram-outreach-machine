# Bot Engagement Controls Formatting And Tests

Inline control, formatting, safety, and test contracts for engagement bot surfaces.

## Inline Controls

Recommended callback prefixes:

```text
eng:home
eng:admin
eng:c:<status>:<offset>
eng:cd:<candidate_id>
eng:ca:<candidate_id>
eng:cr:<candidate_id>
eng:cs:<candidate_id>
eng:ce:<candidate_id>
eng:t:list:<status>:<offset>
eng:t:open:<target_id>
eng:t:perm:<target_id>:<j|d|p>:<0|1>
eng:t:approve:<target_id>
eng:t:reject:<target_id>
eng:p:list:<offset>
eng:p:open:<profile_id>
eng:p:preview:<profile_id>
eng:p:activate:<profile_id>
eng:topic:list:<offset>
eng:topic:open:<topic_id>
eng:style:list:<scope>:<offset>
eng:style:open:<rule_id>
eng:set:open:<community_id>
```

The exact names may change during implementation if needed to preserve the 64-byte callback limit.
The important contract is that engagement callbacks stay inside the `eng:*` namespace and route
only through bot API-client methods.

## Message Formatting

Candidate cards should show:

- send readiness summary
- candidate ID
- community title and username when available
- topic name
- status and expiry
- capped source excerpt
- detected reason
- suggested reply
- final reply when different from the suggestion
- prompt profile and version
- risk notes
- next safe actions

Target cards should show:

- community readiness summary
- target ID
- submitted reference
- resolved community when available
- status
- `allow_join`, `allow_detect`, and `allow_post`
- last error when present
- next safe actions

Prompt cards should show:

- profile ID
- name and active state
- version
- model, temperature, and max output tokens
- output schema
- capped system and user-template previews
- next safe actions

Style cards should show:

- rule ID
- scope and scope ID
- active state
- priority
- capped rule text
- next safe actions

Formatting rules:

- Put the operator-facing summary and next safe action above raw IDs and backend fields.
- Prefer compact cards over long lists.
- Use plain-text visual hierarchy first: short emoji/glyph markers, labeled fields, and section
  headers must remain readable even when Telegram parse modes are disabled.
- Emoji usage should be additive, not decorative overload: keep the icon count low and preserve a
  clear text label for every action and status.
- Show only state-relevant actions on default cards; move diagnostic and advanced actions into detail
  views.
- Truncate source excerpts before final reply text.
- Never truncate final reply text in a send confirmation card. If it is too long for Telegram,
  split the confirmation into multiple messages.
- Never expose sender identity, phone numbers, full account secrets, raw prompt internals that are
  not meant for operators, or person-level scores.

## Safety Rules

- Approval and sending remain separate.
- Queueing a send requires an approved candidate.
- The bot must never offer send controls for `needs_review`, `rejected`, `expired`, or `sent`
  candidates.
- The bot must never create seed rows from engagement target commands.
- Engagement target permissions are engagement-only and must not change community discovery,
  collection, or analysis state.
- All target, prompt, style, topic, candidate edit, approval, send, and action views must preserve
  audit-relevant IDs.
- Any control that can enable posting must show the current permission state before mutation and the
  resulting state after mutation.
- Admin prompt and style controls may not weaken hardcoded backend validation.

## Testing Contract

Minimum tests for implementation:

- Bot API client tests for each new route.
- Formatting tests for target, prompt, style, candidate detail, and revision cards.
- Callback parser tests for every new `eng:*` namespace and the Telegram 64-byte limit.
- Handler tests proving target commands do not call seed APIs.
- Handler tests proving prompt preview does not call generation or send endpoints.
- Conversation-state tests for long prompt, topic, style, and candidate edit flows.
- Permission tests for admin-only commands once backend admin permission exists.
- Safety tests proving send controls appear only for approved candidates.
- Regression tests proving phone numbers, sender identity, and person-level scores are absent from
  bot messages.

## Open Questions

- Admin permission now prefers backend capabilities. The shipped bot still has a transitional
  `TELEGRAM_ADMIN_USER_IDS` allowlist for rollout fallback when backend capabilities are
  unconfigured or unavailable.
- Prompt duplicate and rollback are now first-class API routes.
- Should engagement target approval create default community engagement settings, or remain a
  separate explicit settings action?
- Assigned engagement accounts currently render as account IDs plus masked labels from
  `/api/debug/accounts` when available.
- Should long edit drafts survive bot restarts, or is short-lived in-process state enough for the
  first slice?
