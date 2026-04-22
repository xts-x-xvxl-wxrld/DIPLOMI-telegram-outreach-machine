# Bot Engagement Implementation Slices 6-7

Detailed prompt-profile and topic/style slice contracts.

### Slice 6: Prompt Profile Admin Controls

Purpose:

Expose prompt profile inspection and administration from the engagement admin cockpit without making
prompt editing part of daily candidate review.

Required commands:

```text
/engagement_prompts
/engagement_prompt <profile_id>
/engagement_prompt_versions <profile_id>
/engagement_prompt_preview <profile_id>
/create_engagement_prompt <name> | <description_or_dash> | <model> | <temperature> | <max_output_tokens> | <system_prompt> | <user_prompt_template>
/activate_engagement_prompt <profile_id>
/duplicate_engagement_prompt <profile_id> <new_name>
/edit_engagement_prompt <profile_id> <field>
/rollback_engagement_prompt <profile_id> <version_number>
```

Editable fields:

- `name`
- `description`
- `model`
- `temperature`
- `max_output_tokens`
- `system_prompt`
- `user_prompt_template`

Required inline controls:

- Open profile detail.
- Preview rendered prompt.
- View versions.
- Edit allowlisted fields.
- Duplicate profile when supported by the API.
- Activate profile with confirmation.
- Roll back to a version with confirmation.

Rules:

- Prompt profile controls belong under `Engagement Admin -> Advanced`.
- Preview is render-only unless a later spec introduces an explicitly named test-generation route.
- Prompt activation must show profile name, version, model, temperature, token limit, and output
  schema before confirmation.
- Prompt edits must create immutable backend versions.
- The bot may reject unknown field names and obvious unsupported prompt variables before calling the
  API, but backend validation remains authoritative.
- The bot must never display sender identity or private account metadata in prompt previews.
- Prompt profile changes are admin-only once the permission boundary exists.

API dependencies:

```http
GET  /api/engagement/prompt-profiles
POST /api/engagement/prompt-profiles
GET  /api/engagement/prompt-profiles/{profile_id}
PATCH /api/engagement/prompt-profiles/{profile_id}
POST /api/engagement/prompt-profiles/{profile_id}/activate
POST /api/engagement/prompt-profiles/{profile_id}/preview
GET  /api/engagement/prompt-profiles/{profile_id}/versions
POST /api/engagement/prompt-profiles/{profile_id}/duplicate
POST /api/engagement/prompt-profiles/{profile_id}/rollback
```

Duplicate and rollback controls use first-class backend routes in the shipped implementation.

Tests:

- Prompt preview does not call generation or send endpoints.
- Long prompt edits use the shared edit preview/save/cancel flow.
- Activation requires explicit confirmation.
- Unknown prompt fields are rejected.
- Unsupported prompt variables are rejected or surfaced from API validation.
- Version cards show enough metadata to explain what would activate or roll back.
### Slice 7: Topic Examples And Style Rules

Purpose:

Let admins tune what the system notices and how replies should sound through topic examples,
keyword edits, topic guidance, and style rules.

Required topic commands:

```text
/engagement_topic <topic_id>
/topic_good_reply <topic_id> | <example>
/topic_bad_reply <topic_id> | <example>
/topic_remove_example <topic_id> <good|bad> <index>
/topic_keywords <topic_id> <trigger|negative> <comma_keywords>
/edit_topic_guidance <topic_id>
```

Required style commands:

```text
/engagement_style [scope] [scope_id]
/engagement_style_rule <rule_id>
/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>
/edit_style_rule <rule_id>
/toggle_style_rule <rule_id> <on|off>
```

Required inline controls:

- Open topic detail from topic lists.
- Add good example.
- Add bad example.
- Remove good or bad example by index until examples have stable IDs.
- Edit trigger and negative keywords.
- Edit topic guidance with the shared long-text flow.
- Open style rule detail.
- Filter style rules by scope.
- Create, edit, activate, and deactivate style rules.

Rules:

- Topic screens should use operator language: what to notice, what to avoid, and what useful replies
  sound like.
- Good examples are desired-shape guidance, not templates to copy word for word.
- Bad examples are avoid-this guidance and must never be presented as candidate text.
- Keyword edits replace the selected keyword list unless a later API exposes add/remove operations.
- Style rules may make replies stricter, shorter, clearer, or more contextual.
- Style rules may not permit DMs, impersonation, hidden sponsorship, fake consensus, harassment,
  moderation evasion, unsafe link behavior, or disabling approval.
- Style rule scope and priority must be visible in every style rule card.

API dependencies:

```http
GET    /api/engagement/topics/{topic_id}
PATCH  /api/engagement/topics/{topic_id}
POST   /api/engagement/topics/{topic_id}/examples
DELETE /api/engagement/topics/{topic_id}/examples/{example_type}/{index}

GET    /api/engagement/style-rules
POST   /api/engagement/style-rules
GET    /api/engagement/style-rules/{rule_id}
PATCH  /api/engagement/style-rules/{rule_id}
```

Tests:

- Good and bad examples are labeled distinctly in cards and previews.
- Bad examples are not surfaced as reusable reply text.
- Topic keyword parsing handles commas, whitespace, and empty lists consistently.
- Topic guidance edits use preview/save/cancel.
- Style rule scope filters call the API with explicit scope parameters.
- Unsafe guidance remains blocked by backend validation.
