# Bot Engagement Config Editing

Editable configuration map, conversation-state editing model, and API dependencies.

## Config Editing Model

The engagement admin cockpit should let admins edit most engagement configuration from Telegram,
but the bot must remain a control surface, not the source of truth.

Config editing must be reached from intention pages where possible. For example, editing
`allow_detect` should appear to the operator as changing whether a community is watched, and editing
topic trigger keywords should appear as tuning what the system notices. Raw field names may be shown
in advanced detail cards, logs, and tests, but should not be the primary label in normal use.

Every editable engagement setting should follow the same contract:

1. The backend owns the persisted value.
2. The API exposes a typed route for reading and updating that value.
3. The service layer validates safety, bounds, state transitions, and authorization.
4. The bot renders the current value, collects the proposed value, shows a preview or before/after
   confirmation, and then calls the API.
5. The mutation creates audit or version history when it can affect outbound behavior.

The bot must not implement a generic "edit any database column" surface. Each editable field must be
explicitly allowlisted by entity, field name, value type, and admin requirement.

Recommended editable field metadata:

```text
entity
field
label
value_type
requires_confirmation
admin_only
```

Supported first implementation value types:

- `text`
- `long_text`
- `int`
- `float`
- `bool`
- `enum`
- `time`
- `uuid`
- `keyword_list`

Short values may use commands or inline toggles. Long text values should use conversation-state
editing. Risky values, including posting permission, prompt activation, assigned account changes,
and long instruction changes, must show a confirmation before saving.

### Editable Config Map

The admin cockpit should expose these editable areas.

| Area | Editable fields | Notes |
|---|---|---|
| Engagement targets | `notes`, status transitions, `allow_join`, `allow_detect`, `allow_post` | Approval and permission changes require confirmation and before/after display. |
| Community settings | `mode`, `max_posts_per_day`, `min_minutes_between_posts`, quiet hours, assigned engagement account, allowed join/post flags where supported | MVP edits must preserve `reply_only=true` and `require_approval=true`. |
| Prompt profiles | `name`, `description`, `model`, `temperature`, `max_output_tokens`, `system_prompt`, `user_prompt_template` | Prompt edits create immutable backend versions. Activation is separate and confirmed. |
| Topics | `name`, `description`, `stance_guidance`, `trigger_keywords`, `negative_keywords`, good examples, bad examples, `active` | The bot should present two topic-guidance prompts: "What kind of conversation are we looking for?" and "What position should we take?" Bad examples are never templates to copy. |
| Style rules | `name`, `priority`, `rule_text`, `active` | The bot should frame style rules as: "How should this account sound in this community?" Scope may be immutable after creation in the first implementation. |
| Candidates | `final_reply`, approval/rejection/send state | Final replies are editable only before terminal states. Sending remains separate from approval. |
| Account assignment | assigned engagement account for a community | Only engagement-pool accounts are valid. Bot output must not expose full phone numbers. |

### Instruction Inputs

Written instruction fields include prompt profile prompts, topic guidance, topic good/bad examples,
style rules, and manually edited candidate replies.

These fields are operator/admin-authored configuration. They may be assisted by future draft helpers,
but generated suggestions must be treated as drafts only. A generated or inferred instruction must
not become active until an admin reviews it and explicitly saves it.

The bot should label instruction fields clearly:

- Prompt profile text controls the detection/drafting prompt.
- Topic guidance has two operator-facing values: what kind of conversation to look for, and what
  position to take when that conversation appears.
- Good examples show desired reply shape.
- Bad examples show what to avoid and must be passed to the model only as negative examples.
- Style rules tune how the account should sound in this community, including voice, brevity,
  disclosure, and community/topic-specific constraints.
- Candidate final reply is the exact text eligible for approval and eventual sending.

### Safety Floor

Editable configuration must never weaken hard safety rules. The backend and workers must continue to
enforce:

- no DMs
- no automatic sending in MVP
- no impersonation or fake personal experience
- no hidden sponsorship or fake consensus
- no person-level scoring, ranking, or targeting
- no bypassing operator approval
- no disabling audit logs
- no outbound behavior from collection, discovery, expansion, or analysis workers

If an editable prompt, topic, style rule, or reply conflicts with these rules, backend validation or
worker preflight must reject, skip, or fail closed.

## Conversation-State Editing

Some controls need multi-message input because Telegram command arguments are awkward for long text.

Supported first-state flows:

- edit prompt system prompt
- edit prompt user template
- edit topic guidance
- edit style rule text
- edit candidate final reply

State machine:

```text
start edit
  -> bot records pending edit type, object ID, field, and operator ID
  -> operator sends replacement text
  -> bot calls preview or validation endpoint
  -> bot shows preview plus Save and Cancel controls
  -> Save calls the API mutation
  -> Cancel clears pending state
```

Rules:

- Pending edits are scoped to the operator's Telegram user ID.
- Pending edits expire after a short timeout, recommended 15 minutes.
- A new command from the same operator cancels or supersedes the pending edit after warning.
- The bot should not persist long edit text outside the existing bot process unless a future spec
  introduces durable draft storage.

## API Dependencies

The bot should use existing or planned engagement API routes only.

Required for the expanded controls:

```http
GET    /api/engagement/targets
GET    /api/engagement/targets/{target_id}
POST   /api/engagement/targets
PATCH  /api/engagement/targets/{target_id}
POST   /api/engagement/targets/{target_id}/resolve-jobs
POST   /api/engagement/targets/{target_id}/join-jobs
POST   /api/engagement/targets/{target_id}/detect-jobs

GET    /api/engagement/prompt-profiles
POST   /api/engagement/prompt-profiles
GET    /api/engagement/prompt-profiles/{profile_id}
PATCH  /api/engagement/prompt-profiles/{profile_id}
POST   /api/engagement/prompt-profiles/{profile_id}/activate
POST   /api/engagement/prompt-profiles/{profile_id}/duplicate
POST   /api/engagement/prompt-profiles/{profile_id}/rollback
POST   /api/engagement/prompt-profiles/{profile_id}/preview
GET    /api/engagement/prompt-profiles/{profile_id}/versions

GET    /api/engagement/style-rules
GET    /api/engagement/style-rules/{rule_id}
POST   /api/engagement/style-rules
PATCH  /api/engagement/style-rules/{rule_id}

GET    /api/engagement/topics/{topic_id}
POST   /api/engagement/topics/{topic_id}/examples
DELETE /api/engagement/topics/{topic_id}/examples/{example_type}/{index}
GET    /api/engagement/candidates/{candidate_id}
GET    /api/engagement/candidates/{candidate_id}/revisions
POST   /api/engagement/candidates/{candidate_id}/edit
POST   /api/engagement/candidates/{candidate_id}/expire
POST   /api/engagement/candidates/{candidate_id}/retry
```

If an API route is missing, the bot slice should add the API route first or keep the related bot
control hidden.
