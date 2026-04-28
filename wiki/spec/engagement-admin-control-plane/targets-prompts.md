# Engagement Admin Targets And Prompts

Control separation, target, prompt profile, and prompt variable contracts.

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
/engagement_prompt_versions <prompt_profile_id>
/engagement_prompt_preview <prompt_profile_id>
/create_engagement_prompt <name> | <description_or_dash> | <model> | <temperature> | <max_output_tokens> | <system_prompt> | <user_prompt_template>
/activate_engagement_prompt <prompt_profile_id>
/duplicate_engagement_prompt <prompt_profile_id> <new_name>
/edit_engagement_prompt <prompt_profile_id> <field>
/rollback_engagement_prompt <prompt_profile_id> <version_number>
/engagement_style [scope] [scope_id]
/engagement_style_rule <rule_id>
/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>
/edit_style_rule <rule_id>
/toggle_style_rule <rule_id> <on|off>
/engagement_topic <topic_id>
/topic_remove_example <topic_id> <good|bad> <index>
/topic_keywords <topic_id> <trigger|negative> <comma_keywords>
/edit_topic_guidance <topic_id>
/engagement_candidates [status]
/edit_reply <candidate_id> | <new final reply>
/approve_reply <candidate_id>
/send_reply <candidate_id>
```

Core app surfaces may show a handoff action such as `Add to engagement`, but that action must call
the engagement intake API and create an auditable engagement target row. It must not reuse seed
approval as engagement approval.

Callback prefixes should remain under `eng:*`. Admin-only controls may use `eng:admin:*`.

The backend exposes `GET /api/operator/capabilities` for the bot's current Telegram operator
context. The bot sends `X-Telegram-User-Id` and uses the returned `engagement_admin` capability as
the primary admin boundary. When backend capabilities are unconfigured or unavailable, the Telegram
bot may apply a transitional local admin allowlist such as `TELEGRAM_ADMIN_USER_IDS` to hide and
reject admin-only bot mutations early. This fallback is a UX boundary only; backend authorization
remains the source of truth when configured.
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

```

Rules:

- `add_engagement_target` accepts an existing `community_id`, public Telegram username, public link,
  or future invite-link placeholder.
- Public usernames and public links are normalized to a canonical `username:<lowercase_username>`
  submitted reference for audit consistency.
- Re-adding a public ref or resolved community must create a fresh engagement-target row instead of
  reusing an older one, so the same group can participate in multiple engagement workflows.
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
  + community-level summary
  + selected source post or trigger excerpt
  + reply target context, when needed
```

Recent public message batches may be used by detection to find an opportunity, but the drafting
prompt should not include broad past-message history by default. Drafting should receive only the
selected source post or capped trigger excerpt, optional reply context, topic guidance, style rules,
and community-level summary.

Admin access:

- Admins may edit the active profile's `system_prompt` and `user_prompt_template`.
- Admins may choose the model and basic generation parameters within configured backend limits.
- Every edit creates a version row before the profile becomes active.
- The bot should show prompt previews with variables rendered from a real or synthetic candidate
  context.
- The bot should warn before activating a profile that removes key guidance like public-only,
  reply-only, no DMs, no fake consensus, or prefer no reply.
- Prompt activation and rollback require explicit confirmation in the bot.
- Prompt profile detail, preview, version history, duplicate, edit, activate, and rollback controls
  are admin-only. The bot prefers backend capabilities for local hiding/rejection and falls back to
  `TELEGRAM_ADMIN_USER_IDS` only during rollout, while backend authorization remains authoritative.

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
{{style.topic}}
{{source_post.text}}
{{source_post.tg_message_id}}
{{source_post.message_date}}
{{reply_context}}
{{messages}}
{{community_context.latest_summary}}
{{community_context.dominant_themes}}
```

Rules:

- Templates must render with missing optional fields as empty strings or empty arrays.
- Templates must not expose sender username, sender Telegram user ID, phone number, or private
  account metadata.
- Draft-generation templates should prefer `source_post` and `reply_context` over `messages`.
  `messages` is retained for detection/debug compatibility and should not be used to dump broad
  recent chat history into normal drafting prompts.
- Rendered prompt input must keep existing caps: maximum 500 characters for the selected source
  post or reply-context excerpt, maximum 20 messages when detection/debug templates still use
  `messages`, and 64 KB target serialized input unless a future plan changes those limits.
- Candidate rows should store `prompt_profile_id`, `prompt_profile_version_id`, and a compact prompt
  render summary. Full raw prompt storage may be behind a debug flag because prompts can become
  large.
