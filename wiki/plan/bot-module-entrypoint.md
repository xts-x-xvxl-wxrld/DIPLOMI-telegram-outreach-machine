# Bot Module Entrypoint

## Goal

Ensure the Docker bot service keeps running when launched with `python -m bot.main`.

## Context

`docker-compose.yml` starts the bot with `python -m bot.main`. After the bot refactor,
`bot/main.py` became a compatibility export facade for legacy imports while the executable
`main()` function lives in `bot/app.py`. Without a module guard, `python -m bot.main` imports
successfully and exits with code 0, leaving the bot container stopped and silent.

## Implementation

Status: completed.

- Keep `bot.main` compatibility exports unchanged for existing tests and imports.
- Add an `if __name__ == "__main__": main()` guard so the Compose command starts polling.
- Add a focused regression test that executes `bot.main` as a module and proves the polling
  entrypoint is invoked.
- Keep pending-edit cleanup available inside `runtime_access.access_gate` after the runtime shard
  split so authorized commands do not raise on live bot updates.

## Verification

- Run the focused bot entrypoint test.
- Run focused bot access, handler, engagement-handler, entrypoint, and UI coverage if facade or
  runtime access behavior changes.
- Redeploy staging and confirm the bot container remains up.
