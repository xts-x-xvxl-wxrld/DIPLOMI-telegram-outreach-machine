# Engagement Admin Surfaces And Tests

API, bot UX, observability, audit, testing, and open question contracts.

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
POST /api/engagement/prompt-profiles/{profile_id}/duplicate
POST /api/engagement/prompt-profiles/{profile_id}/rollback
POST /api/engagement/prompt-profiles/{profile_id}/preview
GET  /api/engagement/prompt-profiles/{profile_id}/versions

GET  /api/engagement/style-rules
GET  /api/engagement/style-rules/{rule_id}
POST /api/engagement/style-rules
PATCH /api/engagement/style-rules/{rule_id}

GET  /api/engagement/topics/{topic_id}
POST /api/engagement/topics/{topic_id}/examples
DELETE /api/engagement/topics/{topic_id}/examples/{example_type}/{index}

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
