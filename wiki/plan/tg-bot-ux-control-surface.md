# Telegram Bot UX Control Surface Plan

## Goal

Turn the Telegram bot into the primary operator control surface for the seed-first workflow.

The bot should feel native to Telegram instead of acting like a thin command relay that requires the
operator to copy IDs manually between messages.

## Current Gaps

- `/candidates` still follows the older brief-first flow instead of seed groups.
- Seed groups can be listed, but the operator cannot drill into one group cleanly.
- Candidate review relies on typing `/approve <community_id>` and `/reject <community_id>`.
- Job inspection exists, but messages do not offer an easy refresh loop.
- The bot does not expose community detail, snapshot status, or latest analysis in an operator-friendly way.

## UX Slice

Add a Telegram-native operator flow with:

- a persistent reply keyboard for the main control areas
- inline action buttons for seed groups, candidate review, job refresh, and community drill-down
- seed-group detail messages that summarize imported seeds, resolution progress, and next actions
- seed channel status listing for imported rows inside one group
- seed-group candidate review cards with inline approve and reject actions
- community detail messages with latest snapshot, snapshot history, and latest analysis summary

## Backend Additions

Add only the read models needed for the bot UX:

- seed-group candidate list endpoint that merges:
  - resolved manual seed communities
  - batch expansion target communities
- optional seed-group filter support for community listing only if it simplifies operator drill-down

The bot must continue to talk only to the backend API.

## Command Surface

Keep existing commands, but make the primary operator flow:

1. upload CSV
2. `/seeds`
3. open a seed group
4. resolve seeds
5. inspect channels or candidates
6. approve or reject communities inline
7. inspect community detail or job status as needed

Add operator convenience commands for direct linking and fallback:

- `/seed <seed_group_id>`
- `/channels <seed_group_id>`
- `/community <community_id>`
- `/snapshot <community_id>`

## Non-Goals

- no web frontend work
- no raw message display
- no person-level scores
- no expansion-heavy workflow reintroduction unless needed for an existing route
