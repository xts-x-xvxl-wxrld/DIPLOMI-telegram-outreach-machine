# CI Lint Fix Plan

## Goal

Restore the GitHub Actions lint step by addressing Ruff violations without changing API or bot
behavior.

## Scope

- Keep grandfathered API schema declarations lint-clean without increasing the oversized file.
- Preserve bot formatting facade imports while making review formatter re-exports explicit.
- Run the CI lint/fragmentation checks locally before committing.

## Acceptance Criteria

- `python scripts/check_fragmentation.py` passes.
- `ruff check .` passes.
- No engagement API response fields or bot formatter names are removed.
