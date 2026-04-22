# Bot Copy Readability Refresh Plan

## Goal

Improve Telegram bot readability and operator UX by making message cards easier to scan and button
labels clearer, while keeping the bot safe, compact, and compatible with plain-text Telegram sends.

## Problems

- Current bot messages read like raw field dumps instead of operator-friendly status cards.
- Headings, summaries, and next actions do not stand out enough from IDs and backend detail.
- Button labels are functional but bland, so important actions are harder to spot quickly.
- The bot currently sends plain text without parse-mode formatting, so readability improvements need
  to work well without relying on bold/HTML markup.

## Proposed Slice

- Add shared copy helpers for:
  - visual section dividers and headings
  - status/readiness markers
  - compact action-list formatting
  - consistent empty-state and help copy patterns
- Refresh the highest-traffic discovery and engagement messages first:
  - operator cockpit
  - discovery cockpit and help
  - start/help responses
  - seed-group, candidate, community, and job cards
  - engagement home, settings, target, candidate, topic, style, and audit cards
- Refresh common inline button labels so the cockpit feels more guided and less mechanical.
- Preserve existing safety rules, audit-relevant IDs, and callback-length limits.

## Non-Goals

- No handler or workflow redesign.
- No backend contract changes.
- No unsafe Markdown/HTML parse-mode rollout in this slice.
- No hidden mutation shortcuts that weaken review or permission gates.

## Validation

- Extend `tests/test_bot_formatting.py` for the new structure and readability markers.
- Extend `tests/test_bot_ui.py` for renamed button labels where needed.
- Run `python scripts/check_fragmentation.py`.
- Run focused bot formatting/UI tests.
