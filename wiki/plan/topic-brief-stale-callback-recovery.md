# Topic Brief Stale Callback Recovery

## Goal

Keep the draft-instruction wizard usable during local live testing when the in-memory `topic_create`
pending edit unexpectedly disappears before the operator taps inline navigation buttons.

## Scope

- preserve a shadow snapshot of the active topic brief draft in bot runtime state
- restore the draft when topic-brief callbacks arrive and the normal pending edit is missing
- clear the snapshot on intentional save/cancel paths so stale buttons do not resurrect discarded work
- add regression coverage for the Step 7 good-example review case seen in live testing

## Validation

- run `python scripts/check_fragmentation.py`
- run `ruff check .`
- run `pytest -q tests/test_bot_engagement_setup_flows.py tests/test_bot_engagement_wizard_topic_brief.py`
