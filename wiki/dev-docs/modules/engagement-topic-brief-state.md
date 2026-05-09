# Engagement Topic Brief State

## Purpose

Document the bot-side runtime state seam for the draft-instruction topic-brief flow, especially the
recovery path used when inline callbacks arrive after the live pending edit disappears.

## Owns

- `topic_create` pending-edit lifecycle in the bot
- topic-brief callback recovery from a shadow snapshot
- save/cancel cleanup rules for topic-brief snapshots

## Does Not Own

- topic persistence or validation in backend APIs
- task-first engagement wizard step progression outside the topic-create handoff
- style-rule save semantics beyond the bot-side save orchestration

## Read First

- `bot/runtime_topic_brief.py`
- `bot/runtime_topic_brief_flow.py`
- `bot/runtime_context.py`
- `bot/runtime_config_edit.py`

## Entrypoints And Facades

- `_start_topic_create_with_reply()` in `bot/runtime_topic_brief.py`
  - starts or resumes `topic_create`
- `_handle_topic_brief_navigation()` in `bot/runtime_topic_brief.py`
  - handles `Back`, `Skip`, `Add another`, `Continue`, and `Save later`
- `_show_topic_create_pending()` in `bot/runtime_topic_brief_flow.py`
  - refreshes the operator-visible message and updates the shadow snapshot
- `_save_config_edit_callback()` / `_cancel_config_edit_callback()` in `bot/runtime_config_edit.py`
  - clear the snapshot on intentional completion or discard

## Main Dependencies

- `PendingEditStore` in `bot/config_editing.py`
- `WIZARD_RETURN_STORE_KEY` and wizard resume helpers in `bot/engagement_wizard_flow.py`
- `tests/test_bot_engagement_setup_flows.py`
- `tests/test_bot_engagement_wizard_topic_brief.py`

## Invariants And Boundaries

- the live `config_edit_store` remains the primary source of truth while it exists
- the shadow snapshot only exists for `topic_create` and is used to recover from unexpected
  in-memory pending-edit loss during callback handling
- intentional save, cancel, or command interruption must clear the snapshot so stale inline buttons
  cannot resurrect discarded drafts
- `Save later` keeps the snapshot because the operator is expected to resume the same draft later

## Related Tests

- `tests/test_bot_engagement_setup_flows.py`
- `tests/test_bot_engagement_wizard_topic_brief.py`

## Common Change Patterns

- when adding a new topic-brief callback that reads pending state, use the recovery-aware
  `_get_topic_brief_pending(..., restore_missing=True)` path
- when adding a new terminal exit path for `topic_create`, clear the shadow snapshot in the same
  patch

## Footguns

- if a new path clears `config_edit_store` without also clearing the snapshot on intentional exits,
  old inline keyboards can revive a draft the operator meant to abandon
- if a new path reads raw pending state directly, it can bypass recovery and recreate the live-only
  failure seen during local testing

## Open Questions

- the current recovery path protects against lost in-memory pending state inside a healthy bot
  process; a full process restart still loses both stores because neither is persisted
