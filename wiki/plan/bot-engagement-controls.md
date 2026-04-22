# Bot Engagement Controls Plan

Status: active routing plan; detailed historical slice notes live under
`wiki/plan/bot-engagement-controls/`.

## Goal

Expand the Telegram bot engagement cockpit into a safe operator surface for reply review, target
administration, prompt/style controls, topic examples, and advanced settings while keeping daily
review concise.

## Current Context

The plan has already delivered the main engagement cockpit, target admin, config editing, candidate
revision, prompt, topic/style, advanced settings, and admin permission slices. New work should use
this file to route to the relevant detailed shard instead of loading the original full plan.

## Slice Shards

- [Slices 1-5](bot-engagement-controls/slices-1-5.md) - documentation baseline, navigation, target controls, editing foundation, candidate revisions.
- [Slices 6-10](bot-engagement-controls/slices-6-10.md) - prompt profiles, topic/style controls, advanced settings, permissions, release wrap-up.
- [Follow-Ups](bot-engagement-controls/follow-ups.md) - safety confirmations, guided edits, creation flows, menu polish, backend boundaries.

## Next Refactor Guidance

- Extract `eng:admin:*` callback handling from `bot/main.py` before adding new admin workflows.
- Keep `bot/formatting_engagement.py` and `bot/ui_engagement.py` under the code cap as new controls
are added.
- Split tests by workflow surface after production bot handlers have stable module entrypoints.
