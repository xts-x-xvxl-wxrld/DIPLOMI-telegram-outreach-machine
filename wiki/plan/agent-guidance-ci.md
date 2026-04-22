# Agent Guidance CI Plan

Status: complete

## Goal

Reduce failed GitHub Actions runs by making every agent slice prove the same checks locally before
it is committed or pushed.

## Scope

- Tighten `AGENTS.md` and `CLAUDE.md` with local CI parity rules.
- Record that deploy/CI expects fragmentation, Ruff, pytest, and Docker build gates.
- Ignore local pytest scratch directories that can confuse status/staging.
- Fix the fallback Telegram markup classes that currently break bot tests when the real Telegram
  package is not installed.

## Acceptance Criteria

- Agent guidance tells future agents to run `python scripts/check_fragmentation.py`, `ruff check .`,
  and `pytest -q` before committing code/wiki changes.
- Guidance requires noting any skipped local CI gate before pushing.
- Local generated pytest directories remain out of Git and Docker build context.
- Bot fallback markup tests pass without requiring `python-telegram-bot`.
