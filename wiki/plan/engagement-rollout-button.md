# Engagement Rollout Button Plan

## Goal

Expose semantic rollout stats from the Telegram bot operator surface instead of leaving
`/engagement_rollout` as a hidden compatibility-only command.

## Scope

- Add a `Semantic rollout` entry under the engagement `Drafting/audit` surface.
- Reuse the existing aggregate rollout API and formatter.
- Keep the existing slash command as a manual fallback.
- Add focused UI and callback tests without expanding the large legacy bot test shards.

## Acceptance Criteria

- The `Drafting/audit` screen includes a `Semantic rollout` button.
- Tapping the button loads the aggregate rollout summary with inline window shortcuts.
- The summary remains aggregate-only and keeps `Back` plus `Home` navigation.
- `/engagement_rollout [window_days]` still works unchanged.
- Wiki specs and log mention that rollout is now surfaced in the bot.
