# Bot Cockpit Simplification: Implementation And Rollout

## Community Target Card — Permission Row

`format_engagement_target_card` shows:

```text
- Allowed: watch/draft yes, join yes, post reviewed replies yes
```

This row reflects the internal `allow_detect`, `allow_join`, `allow_post`
flags, not the operator-facing sending-mode concept. After the wizard derives
these flags from sending mode, showing raw permission flags is noise and may
confuse operators who see a mismatch.

Replace with:

```text
- Sending mode: Draft
```

Derived from `community_engagement_settings.mode` where available, with
operator-facing labels such as `Draft` and `Auto send`. Fall back to the
permission flag summary only when mode is unset (pre-wizard targets). Raw
permission fields remain in the audit section (`detail=True`).

## Code Map

| File | Changes |
|---|---|
| `bot/formatting_engagement_review.py` | Slim `format_engagement_candidate_card`; move debug fields to detail view. |
| `bot/ui_engagement.py` | Remove `👀 Open` from `engagement_candidate_actions_markup`; remove `Join/Post on/off` from `engagement_settings_markup`; remove `➕ Add target` from `engagement_target_list_markup`; simplify `_target_status_filter_rows` usage. |
| `bot/formatting_engagement.py` | Replace permission row with sending-mode label in `format_engagement_target_card`; remove `format_engagement_admin_limits_home`. |
| `bot/ui_common.py` | Remove or deprecate `ACTION_ENGAGEMENT_ADMIN_LIMITS`. |
| `bot/callback_handlers.py` | Remove `ACTION_ENGAGEMENT_ADMIN_LIMITS` dispatch; remove `ACTION_ENGAGEMENT_TARGET_ADD` from list markup path. |

## Testing Contract

- Unit test: `format_engagement_candidate_card` omits status, scores, deadlines, prompt
  version, and slash command block.
- Unit test: `format_engagement_candidate_card` shows risk notes only when present.
- Unit test: `engagement_candidate_actions_markup` does not emit `ACTION_ENGAGEMENT_CANDIDATE_OPEN`.
- Unit test: `engagement_settings_markup` does not emit `ACTION_ENGAGEMENT_SETTINGS_JOIN`
  or `ACTION_ENGAGEMENT_SETTINGS_POST`.
- Unit test: `engagement_target_list_markup` does not emit `ACTION_ENGAGEMENT_TARGET_ADD`.
- Unit test: `format_engagement_target_card` shows sending-mode label, not raw permission row,
  when mode is set.
- Regression test: `ACTION_ENGAGEMENT_CANDIDATE_OPEN` still routes to the detail view
  via callback and slash command.

```text
pytest tests/test_bot_ui.py tests/test_bot_engagement_handlers.py
```

## Rollout

These changes are independent of each other and can ship as separate small slices.
Recommended order:

1. Candidate card slimming (highest operator impact, no back-navigation changes).
2. Remove `👀 Open` from list buttons.
3. Candidate status filter simplification.
4. Settings screen permission toggle removal.
5. Community list cleanup (redundant Add button, status filter simplification, sending-mode label).
6. Remove Limits screen.

## Engagement Cockpit Migration Contract

The newer task-first cockpit replaces the older community-scoped engagement
surfaces as the operator-primary flow.

Rollout rules:

1. Ship engagement storage plus engagement-scoped write endpoints first.
2. Backfill one engagement record per existing approved community-level setup.
3. Ship the task-first cockpit read model (`home`, approvals, issues, list,
   detail, sent) on top of engagement-scoped state only.
4. Move the bot home and secondary callbacks to the new `op:*` and `eng:*`
   surfaces.
5. Keep older community settings and admin screens as temporary compatibility
   tools only; do not surface them as parallel primary operator entry points.
6. Remove legacy community-scoped writes after no active bot callback depends on
   them.

Operator safety rules:

- never show both the old community-settings home path and the new `Engagements`
  home as competing primary flows
- when opening a migrated surface for legacy data, create or backfill the
  engagement record first instead of rendering mixed-source UI
- if migration state is incomplete, fail closed with short operator copy rather
  than silently falling back to raw permission toggles
