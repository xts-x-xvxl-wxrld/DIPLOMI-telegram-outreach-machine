# Bot Engagement Menu Gap Inventory

Original inventory of exposed and missing engagement bot controls.

## Current Menu Gap Inventory

This inventory records the gap between the current bot engagement menu and the target control
surface in this spec. It should be updated as implementation slices ship.

### Currently Exposed

The current main engagement menu exposes:

- `/engagement` cockpit.
- Inline intention-first `Today`, `Review replies`, `Approved to send`, `Communities`, `Topics`,
  `Settings lookup`, `Recent actions`, and `Admin` buttons, with the `Admin` entry hidden when the
  bot can identify the caller as a non-admin through backend capabilities or the local fallback.
- Candidate queue filters for `needs_review`, `approved`, `failed`, `sent`, and `rejected`.
- Candidate cards with readiness summaries and state-relevant approve, reject, edit, audit, and
  queue-send command hints.
- `/engagement_candidate <candidate_id>` detail cards with capped source excerpt, prompt provenance,
  risk notes, current final reply, revision entrypoint, and state-aware controls.
- `/edit_reply <candidate_id> | <new final reply>` as a pipe-command edit path.
- `/edit_reply <candidate_id>` as a guided reply-edit flow: the bot stores a pending edit by
  Telegram operator ID, accepts the next text message as the proposed final reply, shows a
  preview, and saves or cancels through `eng:edit:save` / `eng:edit:cancel`.
- Candidate detail buttons can start the same guided reply-edit preview/save flow.
- `/candidate_revisions <candidate_id>` shows immutable reply revision history.
- `/expire_candidate <candidate_id>` explicitly moves a reviewable candidate out of the queue when
  the backend permits it.
- `/retry_candidate <candidate_id>` reopens failed candidates for review when the backend permits
  the transition.
- Shared config-editing foundation with explicit editable field metadata, typed parsers for
  text/long-text/int/float/bool/enum/time/UUID/keyword-list values, per-operator pending state,
  15-minute expiry, and entity-specific API save dispatch.
- `/cancel_edit` for discarding the caller's pending guided edit.
- `/engagement_actions [community_id]`.
- `/engagement_settings <community_id>`.
- Community settings cards with readiness summaries before raw mode, permission, and rate-limit
  fields.
- A daily `Settings lookup` page lists approved engagement targets that have resolved communities
  and opens the existing community settings card through the `eng:set:open` callback.
- Resolved target cards include a direct `Settings` button when the backend exposes a community ID.
- Default target, prompt-profile, topic, and style-rule list cards prioritize operator-facing
  labels and keep raw IDs lower or on opened detail cards; audit/detail views still expose IDs,
  raw state, and diagnostic fields.
- Readiness summaries use backend-provided readiness labels or concrete block reasons when present,
  including quiet-hour, rate-limit, account, membership, or posting-block fields, and otherwise fall
  back to conservative local summaries.
- `/set_engagement <community_id> <off|observe|suggest|ready>`.
- `/set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>`.
- `/set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>`.
- `/clear_engagement_quiet_hours <community_id>`.
- `/assign_engagement_account <community_id> <telegram_account_id>`.
- `/clear_engagement_account <community_id>`.
- Community settings cards now show direct command hints for limits, quiet hours, account
  assignment, join, and manual detection.
- Account assignment and account clearing commands now show before/after masked account labels and
  require a confirmation callback before saving.
- Non-admin operators now get read-only target/topic/settings cards where the bot can identify them
  through backend capabilities or the local fallback, and admin-only prompt/style/admin-menu
  callbacks are rejected before protected mutation API calls.
- The bot now prefers `GET /api/operator/capabilities` for engagement admin checks. During rollout,
  it falls back to `TELEGRAM_ADMIN_USER_IDS` only when backend capabilities are unconfigured or the
  endpoint is unavailable.
- Protected backend target, prompt-profile, style-rule, topic, and community engagement-settings
  mutation routes require the backend engagement-admin capability when `ENGAGEMENT_ADMIN_USER_IDS`
  is configured.
- Assigned engagement accounts render as account IDs plus masked-phone labels from
  `/api/debug/accounts` when available.
- `/join_community <community_id>`.
- `/detect_engagement <community_id> [window_minutes]`.
- `/engagement_topics`, `/engagement_topic <topic_id>`, topic creation, topic active-state toggles,
  good/bad topic examples, example removal, keyword updates, and guided topic-guidance editing.
- Topic cards expose inline `Add good example` and `Add bad example` controls. These start a
  conversation-state preview/save flow and persist through
  `POST /api/engagement/topics/{topic_id}/examples`.
- `/engagement_admin` with inline `Communities`, `Topics`, `Voice rules`, `Limits/accounts`,
  `Advanced`, and back-to-engagement buttons.
- `/engagement_targets [status]`, `/engagement_target`, `/add_engagement_target`,
  `/resolve_engagement_target`, `/approve_engagement_target`, `/reject_engagement_target`,
  `/archive_engagement_target`, `/target_permission`, `/target_join`, and `/target_detect`.
- Inline target list filters for all, pending, resolved, approved, failed, rejected, and archived.
- Target cards with readiness summaries before raw target status and permission fields.
- Target cards with add-target, open/detail, resolve, approve, reject, archive, permission toggle,
  target-scoped join, and target-scoped detect controls.
- Target approval now shows an explicit before/after confirmation card before saving, and the API
  mutation happens only from the confirm callback.
- Target posting-permission changes now show an explicit before/after confirmation card before
  saving. Join and detect permission toggles remain direct.
- `/engagement_prompts`, `/engagement_prompt_preview`, and direct prompt activation.
- `/create_engagement_prompt <name> | <description_or_dash> | <model> | <temperature> |
  <max_output_tokens> | <system_prompt> | <user_prompt_template>` creates inactive prompt profiles
  through the prompt profile API, with local rejection of unsupported prompt-template variables when
  possible.
- Prompt profile lists expose an inline `Create profile` button that starts a guided input,
  preview, save, and cancel flow backed by the same prompt profile creation API.
- `/engagement_prompt <profile_id>` detail cards with full profile metadata and capped prompt
  previews.
- `/engagement_prompt_versions <profile_id>` immutable version history with rollback entrypoints.
- `/activate_engagement_prompt <profile_id>` and inline activation now show an explicit
  confirmation card before activation.
- `/duplicate_engagement_prompt <profile_id> <new_name>` and inline default duplication call the
  prompt profile duplicate API.
- `/edit_engagement_prompt <profile_id> <field>` starts the shared guided config-edit flow for
  allowlisted prompt profile fields.
- `/rollback_engagement_prompt <profile_id> <version_number>` and inline rollback controls show an
  explicit confirmation card before calling the rollback API.
- Prompt template edits reject unsupported variables, including sender identity variables, before
  calling the API when possible.
- `/engagement_style [scope] [scope_id]`, `/engagement_style_rule <rule_id>`,
  `/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>`,
  `/edit_style_rule <rule_id>`, and `/toggle_style_rule <rule_id> <on|off>`.
- Style-rule lists now expose scope filters plus inline create, open, edit, and toggle controls.
- Style-rule `Create` now starts a guided compact-input flow, previews the pending rule, and saves
  through `POST /api/engagement/style-rules`.
- Button-led edit entrypoints now start the shared guided edit flow for candidate final replies,
  target notes, prompt profile fields, topic guidance, style-rule text, and community setting
  fields where those cards expose edit buttons.
- Target cards expose admin-only `Edit notes` controls backed by the engagement target API.
- Community settings cards expose admin-only guided edit controls for posting limits, quiet-hour
  start/end, and assigned engagement account. These saves preserve `reply_only=true` and
  `require_approval=true`.
- Admin-only command, callback, and guided-edit save paths now reject locally identified non-admins
  before protected API mutations are called. Daily review, target detail, topic detail, style list,
  settings detail, and audit views remain readable where the backend permits them.

### Missing From Daily Engagement

- `Settings lookup` menu item.

### Missing From Prompt Profiles

- No known Slice 13 prompt-profile creation gaps.

### Missing From Topics And Examples

- No known Slice 13 topic-example creation gaps.

### Missing From Style Rules

- No known Slice 13 style-rule creation gaps.

### Missing Cross-Cutting UX

- Full readiness summaries for membership, account assignment, expiry, rate limits, and quiet-hour
  blocks when those backend fields are exposed to the bot.
- Further progressive disclosure to keep raw IDs and backend fields behind detail/open views on
  every card.
- Button-led entrypoints that start the shared edit flow from target note and settings cards.
- Confirmation flows for risky admin mutations, including prompt activation, posting permission
  changes, target approval, and account assignment.
