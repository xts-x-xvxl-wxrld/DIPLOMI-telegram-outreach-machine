# Engagement Admin Topics Style And Replies

Topic examples, style rules, and editable reply contracts.

## Topic Examples

Topics already support good and bad reply examples. The control plane should make them first-class.

Admin controls should support:

```text
/topic_good_reply <topic_id> | <example>
/topic_bad_reply <topic_id> | <example>
/topic_remove_example <topic_id> <good|bad> <index>
```

Rules:

- Good examples show the desired helpful shape.
- Bad examples show what to avoid.
- Bad examples must be passed to the model as negative examples only.
- Examples are examples, not templates. The model should not copy them word for word.
- The bot may offer inline good/bad example buttons that collect the next message, preview it, and
  save through the same topic examples API.
- Topic guidance and examples are versioned through normal topic updates or an explicit topic
  history table in a later implementation.
## Style Rules

Style rules let admins tune voice and constraints without rewriting the whole prompt.

Recommended table: `engagement_style_rules`

```sql
id                    uuid PRIMARY KEY
scope_type            text NOT NULL
                      -- global | account | community | topic
scope_id              uuid
name                  text NOT NULL
rule_text             text NOT NULL
active                boolean NOT NULL DEFAULT true
priority              int NOT NULL DEFAULT 100
created_by            text NOT NULL
updated_by            text NOT NULL
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()
```

Precedence:

```text
global rules apply first
account rules add sender identity/voice constraints
community rules adapt to group norms
topic rules adapt to the subject
higher priority rules appear later within the same scope
```

Example community style rule:

```text
Keep replies under 3 sentences. Do not include links. Avoid naming our product unless the source
message directly asks for vendor recommendations.
```

Example topic style rule:

```text
When discussing CRM tools, focus on evaluation criteria: setup effort, integrations, export access,
team adoption, and data quality.
```

Rules:

- Style rules may make replies stricter, shorter, or more contextual.
- Style rules may not permit DMs, impersonation, hidden sponsorship, harassment, fake consensus, or
  moderation evasion.
- The bot should offer list, create, edit, activate, deactivate, and preview controls.
- Inline create controls should collect compact scope/name/priority/rule-text input, preview it,
  and call the style-rule create API only after confirmation.
## Editable Candidate Replies

Every generated candidate must be editable before approval and send.

Recommended table: `engagement_candidate_revisions`

```sql
id                    uuid PRIMARY KEY
candidate_id          uuid NOT NULL REFERENCES engagement_candidates(id)
revision_number       int NOT NULL
reply_text            text NOT NULL
edited_by             text NOT NULL
edit_reason           text
created_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (candidate_id, revision_number)
```

Candidate fields:

- `suggested_reply` remains the model draft.
- `final_reply` is the latest admin-approved text.
- `reviewed_by` and `reviewed_at` record approval.
- `engagement_candidate_revisions` records every manual edit.

Workflow:

```text
candidate created with suggested_reply
  -> admin opens candidate
  -> admin edits final reply one or more times
  -> validation runs on each edit
  -> admin approves final reply
  -> admin queues send
```

Bot controls:

```text
/edit_reply <candidate_id> | <new final reply>
/approve_reply <candidate_id>
/send_reply <candidate_id>
```

Inline candidate cards should show:

- source excerpt
- detected reason
- suggested reply
- current final reply when different from the suggestion
- risk notes
- prompt profile/version
- edit, approve, reject, and queue-send controls

Rules:

- Sending must always use `final_reply`.
- If no edit exists, approval copies `suggested_reply` into `final_reply`.
- The bot must show a preview after edit and before approval.
- Edits are validated with the same reply validation rules as generated text.
- Completed sent candidates must not be edited in normal operations.
