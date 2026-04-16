# Direct Telegram Entity Intake Plan

## Goal

Let the operator send one public Telegram username or link to the bot and have the system classify
the target as a channel, group, user, or bot.

## Flow

1. Bot receives text such as `@example` or `https://t.me/example`.
2. Bot sends the handle to the API.
3. API validates public Telegram username/link shape, records a `telegram_entity_intakes` row, and
   queues `telegram_entity.resolve`.
4. Worker acquires a Telethon account, resolves the entity, classifies it, and persists:
   - channels/groups in `communities`
   - users/bots in `users`
   - the intake row as the audit trail linking the submitted handle to the saved row

## Rules

- Bot still talks only to the API.
- API does not call Telethon directly.
- Private invite links are rejected.
- Users/bots are saved only as Telegram identity rows, with no phone numbers and no person-level
  scores.
- Communities remain candidate records until the operator approves or rejects them.
