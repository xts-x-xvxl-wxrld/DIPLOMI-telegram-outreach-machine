# Engagement Manual Simulation Packages

## Goal

Record paste-ready engagement-testing packages in the wiki so an operator can
manually enter topic and engagement wizard content, then use curated sample
messages to verify what should and should not trigger public reply drafting.

## Scope

- keep packages as wiki docs, not repo test fixtures
- make each package self-contained for one topic family
- include:
  - topic wizard text
  - trigger and negative keyword lists
  - engagement wizard text
  - should-trigger message examples
  - should-not-trigger message examples
  - quick review guidance for approve, edit, or reject decisions

## Package Format

Each package should live in `wiki/plan/engagement-manual-simulation-packages/`
and contain:

- package goal
- topic wizard copy
- keyword fields
- engagement wizard copy
- trigger examples
- non-trigger examples
- operator review notes

## Acceptance

- package text is ready to paste into the current bot wizard flow
- examples sound like short Telegram messages rather than formal prompts
- trigger examples create natural openings without depending on hype
- non-trigger examples cover off-topic, spammy, risky, or weak cases
