# TGStat Removal Plan

## Goal

Retire TGStat as a workspace integration and replace TGStat-first group/channel search with a
source-adapter discovery model.

## Locked Decisions

1. TGStat is not an allowed discovery provider.
2. Manual seed CSV import remains the practical MVP seed source.
3. Automated discovery should first find public Telegram usernames or links, then resolve them
   through Telegram before writing `communities`.
4. Web search adapters and Telegram-native search adapters must be optional and capped.
5. Discovery does not call OpenAI and does not ingest raw messages.
6. Existing operator decisions on communities must be preserved during dedupe.

## Replacement Sources

- Manual seed CSV import for known lists and operator research.
- Public web search API adapters with `site:t.me` query patterns.
- Telegram-native search through Telethon as an experimental, account-managed adapter.
- Seed graph expansion from forwards, mentions, linked discussions, and Telegram links.

## Work Items

### Immediate Cleanup

- Remove `TGSTAT_API_TOKEN` from settings and example environment files.
- Remove TGStat-specific community source enum values.
- Remove TGStat-specific metadata from the active SQLAlchemy model.
- Add an Alembic migration that drops the old `communities.tgstat_id` column.
- Update tests that still used TGStat as a fixture source.

### Spec Updates

- Rewrite the discovery spec around source adapters and seed resolution.
- Update architecture, queue, API, database, frontend, bot, and audience-brief specs so their
  current language does not point future agents back to TGStat.
- Update wiki index and append the change to the log.

### Future Implementation

- Add an internal discovery source adapter interface.
- Implement a web-search adapter that returns normalized public Telegram links.
- Add storage for source evidence if match explanations become too large for `match_reason`.
- Consider a capped Telegram-native search adapter after account-rate behavior is measured.

## Acceptance Criteria

- No runtime setting or code enum references TGStat.
- Fresh databases end with no TGStat-specific community metadata after migrations.
- Current specs describe manual seeds, web search, Telegram-native search, and graph expansion as
  the replacement discovery model.
- Tests pass for queue payloads, settings imports, and seed resolution.

## Non-Goals

- Do not edit `wiki/app-high-level.md`.
- Do not implement a web-search provider in this cleanup slice.
- Do not broaden discovery into person search or outreach automation.
