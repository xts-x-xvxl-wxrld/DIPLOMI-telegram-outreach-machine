# Engagement Target Duplicates

## Goal

Allow the same Telegram community to appear in multiple engagement targets so operators can reuse a
group across different engagement workflows.

## Scope

- Remove the engagement-target uniqueness rule on `community_id`.
- Stop target creation from reusing an existing row when the submitted reference matches.
- Keep join/detect/post worker permission gates safe by treating permissions as granted when any
  approved target for the community enables them.
- Update tests and focused engagement specs to match the new contract.

## Validation

- `python scripts/check_fragmentation.py`
- `ruff check .`
- `pytest -q`
