# Topic Create Question Flow Plan

## Goal

Replace the engagement topic create payload prompt with a one-question-at-a-time bot flow so
operators do not have to compose the full topic object in a single message.

## Scope

- Start the engagement topic create wizard from the existing inline `Create topic` control.
- Ask for topic name, guidance, trigger keywords, optional description, and optional negative
  keywords in sequence.
- Keep `/cancel_edit` active throughout the flow.
- Keep the existing confirmation step before the API create call.
- Preserve legacy pipe syntax for `/create_engagement_topic ...` when arguments are supplied so
  older operator habits do not break immediately.

## Notes

- Reuse the existing pending edit store instead of introducing a separate conversation framework.
- Store wizard step metadata alongside the pending edit so the generic text handler can advance the
  flow safely.
- Optional fields should support a simple skip marker instead of forcing blank messages.

## Validation

- Update topic create bot flow tests for step prompts, validation, preview, and save.
- Run `python scripts/check_fragmentation.py`.
- Run `ruff check .`.
- Run `pytest -q`.
