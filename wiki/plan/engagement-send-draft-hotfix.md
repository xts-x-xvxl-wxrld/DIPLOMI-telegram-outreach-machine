# Engagement Send And Draft Hotfix

## Problem

The task-first cockpit can show join audit rows as sent messages because the sent feed reads every
`sent` engagement action instead of reply actions only. The task-first wizard also queues detection
too early: detection can run before target permissions are enabled, or before the assigned account
has joined, so no reply draft is generated.

## Plan

1. Restrict cockpit sent-message feed and home sent-message signal to reply actions only.
2. In task-first confirmation, enable target/settings permissions before any detection enqueue.
3. When the assigned account still needs to join, enqueue join first and let successful join enqueue
   the first manual detection run.
4. Classify Telegram write-permission errors as community access/send-permission blocks.
5. Add focused regression tests for sent-feed filtering, confirm/detect ordering, post-join detect
   enqueueing, and Telethon permission mapping.

## Verification

- `python scripts/check_fragmentation.py`
- `ruff check .`
- `pytest -q`
