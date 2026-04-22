# Bot Engagement Implementation Slices 4-5

Detailed config-editing and candidate-detail slice contracts.

### Slice 4: Config Editing Foundation

Purpose:

Build one shared editing model for the long-text and risky configuration flows used by later slices.
This slice should make edits predictable before adding more editable surfaces.

Required bot capabilities:

- Maintain pending edit state by Telegram operator ID, edit type, object ID, field name, started
  timestamp, and expected value type.
- Expose reusable Save and Cancel callbacks for pending edits.
- Expire pending edits after a short timeout, recommended 15 minutes.
- Cancel or supersede an operator's pending edit when they start another command or edit flow.
- Render before/after confirmations for risky changes.
- Render preview cards for long instruction values before saving.
- Keep callback data compact enough for Telegram's 64-byte callback limit.

Editable field metadata must be explicit and allowlisted. The minimum metadata is:

```text
entity
field
label
value_type
requires_confirmation
admin_only
api_method
```

Supported value types:

- `text`
- `long_text`
- `int`
- `float`
- `bool`
- `enum`
- `time`
- `uuid`
- `keyword_list`

Rules:

- The editing foundation must not expose a generic database-column editor.
- Each save must dispatch to an entity-specific API-client method.
- Risky changes include posting permission, target approval, prompt activation, prompt rollback,
  assigned account changes, and long instruction updates.
- Backend validation remains authoritative for prompt variables, unsafe guidance, account pool
  eligibility, numeric bounds, and state transitions.
- The bot should pre-check malformed values only to produce clearer operator feedback.

Tests:

- Pending edits are scoped to one operator and cannot be saved by another.
- Save without a matching pending edit is rejected.
- Cancel removes only the caller's pending edit.
- Expired edits cannot be saved.
- Long text previews show the submitted value without calling send, generation, Telethon, or worker
  endpoints.
- Risky edits require a confirmation callback before the API mutation is called.

Done when:

- Candidate reply, prompt field, topic guidance, and style rule edit flows can share the same
  pending-edit and confirmation machinery.
- Later slices can register editable fields without adding new state-machine code.
### Slice 5: Candidate Detail, Editing, And Revisions

Purpose:

Make candidate review inspectable and editable before approval. Operators should be able to see the
full safe candidate context, revise final reply text, inspect revision history, and manage failed or
stale candidates.

Required commands:

```text
/engagement_candidate <candidate_id>
/edit_reply <candidate_id> | <new final reply>
/candidate_revisions <candidate_id>
/expire_candidate <candidate_id>
/retry_candidate <candidate_id>
```

Required inline controls:

- Open candidate detail from candidate list cards.
- Start reply edit.
- Save or cancel reply edit preview.
- Approve only after the operator can see the current final reply.
- Send only for approved candidates.
- View audit or revisions from terminal and non-terminal candidates.

Candidate detail cards should show:

- send readiness summary
- candidate ID
- community title and username when available
- topic name
- status and expiry
- capped source excerpt
- detected reason
- suggested reply
- current final reply
- prompt profile and version when available
- risk notes
- revision count when available
- next safe actions

Rules:

- Source excerpts must be capped.
- Sender identity, phone numbers, private account metadata, and person-level scores must never be
  shown.
- The exact final reply must not be truncated in approval or send confirmations. Split long
  confirmations across messages if needed.
- Sent, rejected, and expired candidates are read-only in normal controls.
- Approval and send remain separate.
- Retry is available only when the backend says the failed state is retryable.
- Expire is an explicit operator action and should leave an audit trail when the API supports it.

API dependencies:

```http
GET  /api/engagement/candidates/{candidate_id}
GET  /api/engagement/candidates/{candidate_id}/revisions
POST /api/engagement/candidates/{candidate_id}/edit
POST /api/engagement/candidates/{candidate_id}/expire
POST /api/engagement/candidates/{candidate_id}/retry
```

If detail, revisions, expire, or retry endpoints are missing, hide the related inline control and
return a clear command response instead of approximating behavior from list data.

Tests:

- Candidate detail formatting omits sender identity and private metadata.
- Editing creates a revision through the API and refreshes the candidate card.
- Approval uses the latest valid final reply.
- Send controls appear only for approved candidates.
- Terminal candidates do not expose edit controls.
- Failed non-retryable candidates do not expose retry controls.
