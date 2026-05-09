# Engagement Prompt Profiles

## Purpose

Document how engagement detection chooses draft instructions, where the fallback text lives, and
which code paths need to stay aligned when the default drafting voice changes.

## Owns

- active prompt-profile selection for engagement detection
- fallback system prompt and fallback preview prompt text
- prompt-template rendering for detection and bot preview flows

## Does Not Own

- topic guidance, examples, or style-rule authoring semantics
- task-first cockpit review and approval behavior
- send-time validation and posting guards

## Read First

- `backend/services/community_engagement_prompts.py`
- `backend/workers/engagement_detect_prompt.py`
- `backend/workers/engagement_detect_openai.py`
- `backend/workers/engagement_detect_types.py`

## Entrypoints And Facades

- `select_active_prompt_profile()` in `backend/services/community_engagement_prompts.py`
  - loads the newest active DB-backed prompt profile, or returns the fallback preview when none is active
- `_build_prompt_runtime()` in `backend/workers/engagement_detect_prompt.py`
  - picks the system prompt, user template, model, and generation settings used by `engagement.detect`
- `detect_with_openai()` in `backend/workers/engagement_detect_openai.py`
  - passes the chosen system prompt as OpenAI `instructions` and the rendered template as the user input
- `_default_prompt_preview()` in `backend/services/community_engagement_prompts.py`
  - supplies the bot/API preview defaults when no prompt profile exists yet

## Main Dependencies

- `EngagementPromptProfile` and `EngagementPromptProfileVersion` in `backend/db/models_engagement.py`
- prompt/profile CRUD routes in `backend/api/routes/engagement_prompts_style.py`
- `render_prompt_template()` in `backend/services/community_engagement_prompts.py`

## Invariants And Boundaries

- live draft-generation instructions come from the currently active prompt profile when one exists
- the hardcoded `DETECTION_INSTRUCTIONS` constant is only the fallback system prompt
- the fallback preview prompt in `_default_prompt_preview()` should stay semantically aligned with
  `DETECTION_INSTRUCTIONS`, otherwise previewing a missing-profile setup can diverge from live detection
- changing the code defaults does not rewrite existing prompt-profile rows in the database
- continuation candidates are special: the worker appends a global continuation-mode addendum to the
  chosen system prompt and rendered user prompt so older saved prompt profiles still behave like
  threaded follow-up prompts instead of root-reply prompts

## Common Change Patterns

- when changing the default engagement voice, update both `DETECTION_INSTRUCTIONS` and
  `_default_prompt_preview().system_prompt`
- when changing the prompt-variable contract, update `_ALLOWED_PROMPT_VARIABLES`, the rendering
  paths, and the control-plane spec together
- when changing continuation-specific instructions, update the worker append logic as well as the
  continuation developer doc; editing prompt-profile defaults alone will not cover already-saved
  active profiles

## Footguns

- editing only the fallback constant will not affect environments that already have an active
  prompt profile saved in the database
- editing only the preview default can make the bot show a prompt that production detection never uses
- the fallback template and active-profile template share validation rules, so new variables must be
  allowed centrally before they can appear in either path
