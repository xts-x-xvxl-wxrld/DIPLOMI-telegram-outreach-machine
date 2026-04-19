# Engagement Admin Control Plane Spec

## Purpose

The engagement admin control plane is the operator-only surface for deciding which Telegram
communities may be used for engagement, how the OpenAI drafting prompt is assembled, and what final
reply text is approved before a managed account posts publicly.

This spec extends `wiki/spec/engagement.md`. The core engagement worker remains conservative:

```text
explicit engagement target
  -> optional join
  -> detect approved topic moments
  -> draft with admin-controlled prompt inputs
  -> admin edits or rejects
  -> admin explicitly queues send
  -> public reply is logged
```

The control plane must be separate from seed discovery, expansion, collection, and core app review.
Adding a seed group must never automatically make that community available for engagement.

## Goals

- Keep engagement communities in a separate manual intake flow from regular seed add/import.
- Give admins bot-level access to prompt profiles, user prompt templates, examples, model
  parameters, topic guidance, and community style rules that feed the drafting model.
- Allow admins to edit every candidate reply before approval and sending.
- Preserve hard safety constraints outside the editable prompt text.
- Keep core app controls and engagement controls visually and operationally separate.
- Store enough prompt, edit, and send history to explain why a reply was drafted and what was
  actually sent.

## Non-Goals

- No automatic sending.
- No direct messages.
- No top-level posts in the first implementation.
- No person-level scoring, ranking, or persuasion profiles.
- No hidden identity behavior or fake consensus.
- No seed import side effect that enables engagement.
- No prompt edit that can disable non-prompt safety validation.

## Control Separation

Engagement controls must live in their own command namespace and API namespace.

Recommended bot entrypoints:

```text
/engagement_admin
/engagement_targets
/add_engagement_target <telegram_link_or_username_or_community_id>
/engagement_settings <engagement_target_or_community_id>
/engagement_prompts
/engagement_prompt <prompt_profile_id>
/engagement_style <scope> <id>
/engagement_candidates [status]
/edit_reply <candidate_id> | <new final reply>
/approve_reply <candidate_id>
/send_reply <candidate_id>
```

Core app surfaces may show a handoff action such as `Add to engagement`, but that action must call
the engagement intake API and create an auditable engagement target row. It must not reuse seed
approval as engagement approval.

Callback prefixes should remain under `eng:*`. Admin-only controls may use `eng:admin:*`.

## Engagement Targets

Engagement targets are the explicit list of communities that the engagement module may consider.
They are separate from seed groups.

Recommended table: `engagement_targets`

```sql
id                    uuid PRIMARY KEY
community_id          uuid REFERENCES communities(id)
submitted_ref         text NOT NULL
submitted_ref_type    text NOT NULL
                      -- community_id | telegram_username | telegram_link | invite_link
status                text NOT NULL DEFAULT 'pending'
                      -- pending | resolved | approved | rejected | failed | archived
allow_join            boolean NOT NULL DEFAULT false
allow_detect          boolean NOT NULL DEFAULT false
allow_post            boolean NOT NULL DEFAULT false
notes                 text
added_by              text NOT NULL
approved_by           text
approved_at           timestamptz
last_error            text
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (community_id)
```

Rules:

- `add_engagement_target` accepts an existing `community_id`, public Telegram username, public link,
  or future invite-link placeholder.
- Resolving a target may reuse the existing Telegram entity resolver, but the queue job must be an
  engagement job, not a seed job.
- A target must be `approved` before `community.join`, `engagement.detect`, or `engagement.send`
  can operate on the community.
- `allow_join`, `allow_detect`, and `allow_post` are engagement permissions only. They do not change
  seed discovery, expansion, or collection behavior.
- If a community also exists as a seed, the engagement target still owns engagement permission.
- Bulk import may be added later, but every imported row remains an engagement target, not a seed.

## Prompt Profiles

Prompt profiles define the editable OpenAI instructions for engagement detection and drafting.
Admins should be able to view, create, duplicate, edit, activate, deactivate, preview, and roll back
prompt profiles from the bot.

Recommended table: `engagement_prompt_profiles`

```sql
id                    uuid PRIMARY KEY
name                  text NOT NULL
description           text
active                boolean NOT NULL DEFAULT false
model                 text NOT NULL
temperature           numeric NOT NULL DEFAULT 0.2
max_output_tokens     int NOT NULL DEFAULT 1000
system_prompt         text NOT NULL
user_prompt_template  text NOT NULL
output_schema_name    text NOT NULL DEFAULT 'engagement_detection_v1'
created_by            text NOT NULL
updated_by            text NOT NULL
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()
```

Recommended table: `engagement_prompt_profile_versions`

```sql
id                    uuid PRIMARY KEY
prompt_profile_id     uuid NOT NULL REFERENCES engagement_prompt_profiles(id)
version_number        int NOT NULL
model                 text NOT NULL
temperature           numeric NOT NULL
max_output_tokens     int NOT NULL
system_prompt         text NOT NULL
user_prompt_template  text NOT NULL
output_schema_name    text NOT NULL
created_by            text NOT NULL
created_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (prompt_profile_id, version_number)
```

Prompt assembly should use this order:

```text
immutable safety floor
  + active prompt profile system prompt
  + rendered user prompt template
  + global style rules
  + account style rules
  + community style rules
  + topic guidance and examples
  + recent public message context
  + community-level analysis context
```

Admin access:

- Admins may edit the active profile's `system_prompt` and `user_prompt_template`.
- Admins may choose the model and basic generation parameters within configured backend limits.
- Every edit creates a version row before the profile becomes active.
- The bot should show prompt previews with variables rendered from a real or synthetic candidate
  context.
- The bot should warn before activating a profile that removes key guidance like public-only,
  reply-only, no DMs, no fake consensus, or prefer no reply.

Safety floor:

- Some safety is not a prompt. It remains hardcoded validation and worker preflight.
- Admin prompt access must not disable no-DM validation, link policy, reply length limits,
  required approval, rate limits, reply-only mode, or audit logging.
- If the admin prompt conflicts with the safety floor, the safety floor wins and the candidate is
  skipped or marked failed.

## Prompt Variables

The user prompt template may reference only approved variables.

Required variables:

```text
{{community.title}}
{{community.username}}
{{community.description}}
{{topic.name}}
{{topic.description}}
{{topic.stance_guidance}}
{{topic.trigger_keywords}}
{{topic.negative_keywords}}
{{topic.example_good_replies}}
{{topic.example_bad_replies}}
{{style.global}}
{{style.account}}
{{style.community}}
{{messages}}
{{community_context.latest_summary}}
{{community_context.dominant_themes}}
```

Rules:

- Templates must render with missing optional fields as empty strings or empty arrays.
- Templates must not expose sender username, sender Telegram user ID, phone number, or private
  account metadata.
- Rendered prompt input must keep existing caps: maximum 20 messages, 500 characters per message,
  and 64 KB target serialized input unless a future plan changes those limits.
- Candidate rows should store `prompt_profile_id`, `prompt_profile_version_id`, and a compact prompt
  render summary. Full raw prompt storage may be behind a debug flag because prompts can become
  large.

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

## API Surface

Recommended new or expanded endpoints:

```http
GET  /api/engagement/targets
POST /api/engagement/targets
PATCH /api/engagement/targets/{target_id}
POST /api/engagement/targets/{target_id}/resolve-jobs
POST /api/engagement/targets/{target_id}/join-jobs
POST /api/engagement/targets/{target_id}/detect-jobs

GET  /api/engagement/prompt-profiles
POST /api/engagement/prompt-profiles
GET  /api/engagement/prompt-profiles/{profile_id}
PATCH /api/engagement/prompt-profiles/{profile_id}
POST /api/engagement/prompt-profiles/{profile_id}/activate
POST /api/engagement/prompt-profiles/{profile_id}/preview
GET  /api/engagement/prompt-profiles/{profile_id}/versions

GET  /api/engagement/style-rules
POST /api/engagement/style-rules
PATCH /api/engagement/style-rules/{rule_id}

POST /api/engagement/topics/{topic_id}/examples
DELETE /api/engagement/topics/{topic_id}/examples/{example_id}

POST /api/engagement/candidates/{candidate_id}/edit
```

API rules:

- All routes require operator auth.
- Admin-only prompt and style routes require an admin permission, not just a regular operator.
- API routes may enqueue jobs, validate state, and persist configuration. They must not call
  Telethon or OpenAI directly.
- Preview endpoints may render prompts and may call OpenAI only if explicitly named as a test
  generation endpoint in a later plan. The first preview can be render-only.

## Bot UX

The Telegram bot should separate daily engagement review from admin configuration.

Recommended menus:

```text
Engagement
  Candidates
  Targets
  Actions

Engagement Admin
  Targets
  Prompt profiles
  Topics and examples
  Style rules
  Settings
```

Short commands are acceptable for ID-heavy edits. Conversation-state flows may be added later for
long prompt editing, because Telegram command text is awkward for multi-paragraph prompts.

For long prompt edits, the bot may support:

- "Start editing prompt" button.
- Admin sends the new prompt text as the next message.
- Bot shows a rendered preview.
- Admin confirms save and activation.

## Observability And Audit

Every admin-controlled change that can affect model output or outbound text should be auditable.

Audit events should include:

- engagement target added, resolved, approved, rejected, archived
- prompt profile created, edited, activated, rolled back
- style rule created, edited, activated, deactivated
- topic example added or removed
- candidate edited
- candidate approved
- send queued
- send result

Candidate and action views should expose the prompt profile/version and final reply source:

```text
reply_source = generated | edited
prompt_profile_version = name#version
```

## Testing Contract

Minimum tests for implementation:

- engagement target intake does not create seed groups or seed import rows
- joins/detects/sends reject communities without approved engagement targets
- prompt profile CRUD creates immutable version rows
- active prompt selection is deterministic
- prompt rendering includes style rules, topic examples, and no sender identity
- unsafe prompt/profile edits do not bypass validation
- topic good/bad examples are passed in the correct prompt fields
- style-rule precedence is stable
- candidate edit stores revisions and updates `final_reply`
- approval uses the latest valid `final_reply`
- send worker sends exactly the approved final text
- bot admin routes require admin operator permission
- bot prompt preview and edit flows truncate safely and avoid exposing private data

## Open Questions

- Should prompt profiles be global only in the first implementation, or should communities be able
  to choose a specific prompt profile?
- Should engagement target approval also create default engagement settings, or should those remain
  two separate admin actions?
- Should long prompt editing happen through Telegram conversation state, a web admin page, or both?
- Should full rendered prompts be stored for every candidate, or only when debug prompt logging is
  enabled?
- Should good/bad reply examples have their own IDs now, or stay as ordered arrays until a later
  migration?
