# Bot Engagement Command Surface

Detailed command contracts for daily review, target, prompt, topic, style, and community controls.

## Command Surface

### Daily Review Commands

Existing commands remain valid:

```text
/engagement
/engagement_candidates [status]
/edit_reply <candidate_id> | <new final reply>
/approve_reply <candidate_id>
/reject_reply <candidate_id>
/send_reply <candidate_id>
/engagement_actions [community_id]
```

Expanded daily commands:

```text
/engagement_candidate <candidate_id>
/candidate_revisions <candidate_id>
/expire_candidate <candidate_id>
/retry_candidate <candidate_id>
```

Rules:

- Command syntax is a traceability and testing surface. The normal operator path should be
  button-led cards from `Today`, `Review replies`, and `Approved to send`.
- `/engagement_candidate` shows one full candidate card with capped source excerpt, suggested
  reply, current final reply, prompt provenance, risk notes, status, expiry, and next actions.
- `/candidate_revisions` shows manual reply revisions and who edited them.
- `/expire_candidate` is an explicit operator action for stale candidates that should leave the
  review queue.
- `/retry_candidate` may move an operationally failed candidate back to a reviewable state only when
  the API permits that transition.

### Target Commands

```text
/engagement_targets [status]
/engagement_target <target_id>
/add_engagement_target <telegram_link_or_username_or_community_id>
/resolve_engagement_target <target_id>
/approve_engagement_target <target_id>
/reject_engagement_target <target_id>
/archive_engagement_target <target_id>
/target_permission <target_id> <join|detect|post> <on|off>
/target_join <target_id>
/target_collect <target_id>
/target_collection_runs <target_id>
/target_detect <target_id> [window_minutes]
```

Rules:

- Target commands power the `Communities` screen. Operator-facing copy should talk about watching,
  drafting, joining, and posting rather than only `allow_*` flags.
- Adding an engagement target must call the engagement target API and must not create seed rows.
- A target must resolve to a community before it can be approved.
- Approval and permission changes must show the current `allow_join`, `allow_detect`, and
  `allow_post` state before and after the action.
- Target-level join and detect controls call target-scoped API routes when available. If the API
  only supports community-scoped routes, the bot must still verify and display the approved target
  gate returned by the API.
- Target-level collection controls call target-scoped API routes, require an approved target with
  detection permission, and show recent collection run status with message/member counts.
- Rejecting or archiving a target forces all permissions off through the API.

### Prompt Profile Commands

```text
/engagement_prompts
/engagement_prompt <profile_id>
/engagement_prompt_versions <profile_id>
/engagement_prompt_preview <profile_id>
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

Rules:

- Prompt profile controls belong under `Advanced` by default. Most day-to-day tuning should use
  `Topics` and `Voice rules`.
- Prompt profile creation creates an inactive profile through `POST /api/engagement/prompt-profiles`
  and may be started from `/create_engagement_prompt` or the inline `Create profile` button.
- Long prompt fields should use conversation-state editing: the admin starts an edit, sends the new
  text as the next message, reviews a rendered preview, then confirms save.
- Every edit creates or references an immutable backend version row.
- Activation must be explicit and should show the profile name, version number, model, temperature,
  and output schema before confirmation.
- Prompt preview is render-only unless a later API endpoint is explicitly named as a generation
  test endpoint.
- The bot must not display or accept unapproved prompt variables.

### Topic Example Commands

Existing topic commands remain valid:

```text
/engagement_topics
/create_engagement_topic
/toggle_engagement_topic <topic_id> <on|off>
/topic_good_reply <topic_id> | <example>
/topic_bad_reply <topic_id> | <example>
```

Expanded topic commands:

```text
/engagement_topic <topic_id>
/topic_remove_example <topic_id> <good|bad> <index>
/topic_keywords <topic_id> <trigger|negative> <comma_keywords>
/edit_topic_guidance <topic_id>
```

Rules:

- `/create_engagement_topic` should default to a guided multi-step flow instead of requiring the
  operator to send the whole topic payload in one message.
- The bot may continue accepting the legacy pipe payload when the command is called with inline
  arguments so existing habits do not break immediately.

- Topic controls should be labeled as "what to notice" and "what to say about it" before showing raw
  keyword arrays.
- Good examples are positive guidance.
- Bad examples are avoid-this guidance and must never be treated as templates to copy.
- Example removal by array index is acceptable until the backend stores examples as first-class
  rows.
- Topic guidance edits may use conversation-state editing because guidance can be multi-paragraph.

### Style Rule Commands

```text
/engagement_style [scope] [scope_id]
/engagement_style_rule <rule_id>
/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>
/edit_style_rule <rule_id>
/toggle_style_rule <rule_id> <on|off>
```

Supported scopes:

- `global`
- `account`
- `community`
- `topic`

Rules:

- Style rule controls should be labeled as `Voice rules` in normal navigation.
- Style rules may make replies stricter, shorter, more contextual, or more transparent.
- Style rules may not permit DMs, impersonation, fake consensus, harassment, moderation evasion, or
  unsafe link behavior.
- The bot should show scope, active state, priority, capped rule text, and last update metadata when
  available.
- Long rule edits should use a preview-and-confirm flow.

### Community Control Commands

Existing commands remain valid:

```text
/engagement_settings <community_id>
/set_engagement <community_id> <off|observe|suggest|ready>
/join_community <community_id>
/detect_engagement <community_id> [window_minutes]
```

Expanded community commands:

```text
/set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>
/set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>
/clear_engagement_quiet_hours <community_id>
/assign_engagement_account <community_id> <telegram_account_id>
/clear_engagement_account <community_id>
```

Rules:

- Community controls should be summarized as readiness, safety limits, and account assignment before
  raw settings fields.
- Limit updates must preserve `reply_only=true` and `require_approval=true`.
- The backend owns numeric bounds. The bot may pre-check obvious malformed values but must rely on
  API validation.
- Quiet hours are interpreted in the deployment/user locale configured for the app.
- Assigned accounts must be engagement-pool accounts. The API validates this; the bot displays the
  error if the account is in the wrong pool.
- The bot must never show full account phone numbers.
