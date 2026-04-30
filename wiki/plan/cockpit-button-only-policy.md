# Cockpit Button-Only Policy

Active cleanup plan for finishing the top-level Telegram bot cockpit migration.

## Goal

Make inline cockpit buttons the only top-level button surface while keeping slash commands and
operator text intake intact.

The durable UX contract lives in:

- `wiki/spec/bot-operator-cockpit.md`
- `wiki/spec/bot-operator-cockpit/navigation.md`
- `wiki/spec/bot-operator-cockpit/entries-rollout.md`

## Scope

- `/start` opens the inline cockpit and clears any old persistent reply keyboard.
- `/help` shows help with inline cockpit navigation.
- Slash commands such as `/seeds`, `/engagement`, `/accounts`, and `/engagement_admin` keep working
  as hidden compatibility entrypoints, but user-facing copy and Telegram's command menu do not
  advertise them.
- CSV uploads and direct Telegram handle/link text intake keep working.
- Old reply-keyboard text labels are not registered as navigation handlers.

## Remaining Slices

1. Remove legacy text-label handlers for the old reply-keyboard labels.
2. Remove the old persistent `main_menu_markup()` factory and its legacy UI test.
3. Add a regression test that those labels are no longer registered as `MessageHandler` routes.
4. Keep tests proving `/start` clears the old keyboard without attaching persistent reply markup.
5. Run focused bot handler/UI tests, then the repo's local CI parity gates before merge.

## Acceptance Criteria

- No `MessageHandler(filters.Regex(...))` routes exist for the old top-level labels:
  `Seed Groups`, `Engagement`, `Accounts`, or `Help`.
- No exported markup helper creates the old persistent top-level reply keyboard.
- Slash commands remain registered for the same destinations.
- Bot replies, callback edits, and the startup command menu do not expose slash commands as the
  primary navigation surface.
- `MessageHandler(filters.Document.FileExtension("csv"))` and free-text entity intake remain
  registered after command/callback routes.
- `/start` sends `ReplyKeyboardRemove` followed by an inline cockpit message.
- Operator access checks still apply through the existing global access gate.
