# Engagement Natural Account Behavior

Status: implemented.

## Goal

Make engagement account sends feel less bot-like by wrapping approved public replies in Telegram
presence behavior where it is safe and reversible.

## Source Reference

`git@github.com:RichardAtCT/claude-code-telegram.git` uses a persistent typing heartbeat around
long-running agent work. That repo is bot-api based, so its exact API calls do not transfer to
Telethon user accounts, but the interaction pattern does.

## Slice

1. Keep collection and detection unchanged.
2. In the Telethon engagement send adapter, mark the source reply message as read before sending.
3. Show a short typing action before the outbound reply.
4. Treat presence calls as best effort so read/typing failures do not block an approved send.
5. Add fake-client adapter tests for the presence envelope and best-effort fallback.

## Acceptance

- `send_public_reply` calls Telethon read acknowledgement for the source message.
- `send_public_reply` opens and closes a typing action before sending.
- Reply sends continue when read acknowledgement or typing fails.
- Existing send preflight and audit behavior remains unchanged.
