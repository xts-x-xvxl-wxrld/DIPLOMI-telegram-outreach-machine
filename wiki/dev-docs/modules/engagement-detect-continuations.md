# Engagement Detect Continuations

## Purpose

Document the narrow worker seam that lets engagement detection keep a live Telegram conversation
going after an approved send, even when the follow-up message does not repeat the original topic
keywords.

## Owns

- direct-reply continuation candidate selection inside the detect worker
- account-aware lookup of previously sent managed replies
- topic-scoped continuation reuse so follow-up drafts stay attached to the same engagement topic

## Does Not Own

- send-side continuation cadence and caps
- Telegram collection of reply metadata
- approval queue formatting for continuation drafts

## Read First

- `backend/workers/engagement_detect_process.py`
- `backend/workers/engagement_detect_selection.py`
- `backend/services/engagement_opportunity_cadence.py`
- `tests/test_engagement_detect_worker.py`
- `wiki/spec/engagement/account-behavior.md`

## Entrypoints And Facades

- `_select_trigger_candidates()` in `backend/workers/engagement_detect_selection.py`
  - merges direct continuation candidates with the normal semantic/keyword trigger path
- `_select_direct_continuation_candidates()` in `backend/workers/engagement_detect_selection.py`
  - treats a message as a continuation candidate when its `reply_to_tg_message_id` points at a
    previously sent managed reply from the selected engagement account in the same community/topic
- `process_engagement_detect()` in `backend/workers/engagement_detect_process.py`
  - threads `selected_telegram_account_id` into trigger selection so continuation lookup stays
    account-aware before draft creation
- `classify_candidate_opportunity()` in `backend/services/engagement_opportunity_cadence.py`
  - turns the selected direct reply into a durable `continuation` candidate with `root_candidate_id`

## Invariants And Boundaries

- Direct continuation detection is intentionally conservative: only explicit Telegram replies to a
  previously sent managed message qualify.
- Continuation selection is topic-scoped. The detect worker only reopens the topic whose prior sent
  candidate owns the replied-to Telegram message.
- Continuations bypass keyword and semantic trigger requirements at selection time, but they still
  go through the detector and may still return `should_engage = false`.
- Continuation prompt behavior is global and worker-enforced. The detect worker appends a locked
  continuation-mode system addendum plus a continuation task/user-context suffix even when the
  active prompt profile predates continuation support.
- Duplicate suppression still runs before continuation selection, so an active draft for the same
  follow-up message blocks another candidate.
- `reply_to_tg_message_id` must be preserved on the `DetectionMessage`; candidate classification and
  downstream continuation send cadence depend on it.
- Continuation prompt context is compact on purpose: previous managed reply, recent public follow-up
  replies, deterministic stage/objective heuristics, unresolved question, repetition guard, and a
  short thread summary. It should not dump full chat history by default.

## Related Tests

- `tests/test_engagement_detect_worker.py`
- `tests/test_engagement_send_worker.py`

## Footguns

- If you remove the account ID from `_select_trigger_candidates()`, direct replies can start
  matching unrelated accounts' sent messages in the same community.
- If you broaden continuation selection beyond exact `reply_to_tg_message_id` matches, update the
  account-behavior spec first; semantic "same discussion" continuations are still out of scope.
- If semantic selector plumbing changes, keep `_coerce_detection_message()` copying
  `reply_to_tg_message_id`; otherwise continuation candidates created from wrapped match objects can
  silently fall back to `root`.
