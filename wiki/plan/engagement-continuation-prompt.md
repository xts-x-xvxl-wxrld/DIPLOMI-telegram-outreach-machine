# Engagement Continuation Prompt

Status: active.

## Goal

Make continuation-thread drafting a first-class global prompt mode so direct follow-up replies are
handled as ongoing public conversations instead of generic fresh opportunities.

## Decisions

- Keep continuation behavior global and worker-enforced instead of relying on every saved prompt
  profile to be edited manually.
- Append a continuation-specific system addendum to the active prompt profile or fallback prompt
  whenever the detect worker is drafting a `continuation` candidate.
- Append a continuation-specific user/task suffix with compact thread context, even when the active
  prompt template does not reference new continuation variables directly.
- Extend structured detector output with optional continuation-specific fields without breaking
  existing prompt profiles or reply-candidate storage.
- Keep thread context compact and deterministic: previous managed reply, latest public follow-ups,
  stage/objective heuristics, unresolved question, repetition guard, and thread summary.

## Slices

1. Add continuation prompt contract constants and runtime append logic in the detect prompt builder.
2. Build compact continuation thread context during trigger selection and pass it through to prompt
   assembly.
3. Extend the detector output schema plus stored compact model output to carry continuation metadata.
4. Update specs, prompt-profile docs, and continuation docs so the worker-enforced addendum is part
   of the documented prompt contract.
5. Add targeted tests for continuation prompt rendering and structured-output storage.

## Acceptance

- Continuation candidates always receive the locked continuation system instructions, even with an
  older active prompt profile in the database.
- Continuation candidates always receive a task-oriented user prompt section that explicitly says the
  model is deciding whether to continue the thread and, if yes, to draft the next natural reply.
- Prompt-profile templates may reference new `thread.*` variables, but continuations remain usable
  even when a saved template does not mention them.
- Detector output accepts optional continuation metadata such as `continuation_goal`,
  `answered_question`, and `avoid_repeating`.
- `python scripts/check_fragmentation.py`, `ruff check .`, and `pytest -q` pass.
