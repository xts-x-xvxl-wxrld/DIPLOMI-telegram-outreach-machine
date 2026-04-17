# Telegram Community Discovery

Single-operator Telegram community discovery and monitoring app. The active workflow is seed-first:
the operator imports example Telegram communities, resolves them, expands candidates, reviews them,
then collects community-level data.

## Local Development

```powershell
python -m pip install -e ".[dev]"
pytest -q
ruff check .
```

Local runtime secrets live in `.env`. Keep `.env` out of Git.

## GitHub Upload Checklist

1. Create an empty GitHub repository.
2. Add it as `origin`:

   ```powershell
   git remote add origin git@github.com:<owner>/<repo>.git
   ```

3. Confirm secrets are not tracked:

   ```powershell
   git ls-files .env
   git status --ignored --short .env
   ```

   The first command should print nothing. The second command should show `.env` as ignored.

4. Commit and push:

   ```powershell
   git ci "chore: prepare github and vps pipeline"
   git push -u origin main
   ```

## Safe VPS Workflow

Use separate checkouts for deployment and agent editing:

```text
/srv/telegram-outreach/deploy       # reset-only staging checkout
/srv/telegram-outreach/agent-work   # branch-based coding-agent workspace
```

Production deployment always resets the deploy checkout to `origin/main`, builds the app images,
runs Alembic migrations, and restarts Docker Compose. Coding agents must work on branches in a
separate checkout or worktree, then push those branches to GitHub for CI and review.

## First VPS Setup

On the VPS:

```bash
sudo mkdir -p /srv/telegram-outreach
sudo chown "$USER:$USER" /srv/telegram-outreach
cd /srv/telegram-outreach
git clone git@github.com:<owner>/<repo>.git deploy
git clone git@github.com:<owner>/<repo>.git agent-work
cd deploy
cp .env.example .env
chmod 600 .env
```

Fill the real values in `/srv/telegram-outreach/deploy/.env`.

Enable the optional Telegram bridge when VPS bots or coding agents should exchange short messages
with you through the bot:

```bash
TELEGRAM_BRIDGE_ENABLED=true
TELEGRAM_BRIDGE_INBOX_PATH=data/telegram_bridge_inbox.jsonl
TELEGRAM_BRIDGE_CHAT_ID=<chat-id-from-/bridge>
```

Send `/bridge` to the Telegram bot to see the chat ID and inbox path. Allowlisted plain text
messages are appended to the JSONL inbox. VPS bots can reply with:

```bash
python scripts/telegram_bridge_send.py --sender worker-bot --text "collection finished"
```

Manual deploy:

```bash
cd /srv/telegram-outreach/deploy
bash scripts/vps-deploy.sh origin/main
```

## GitHub Secrets for Staging Auto Deploy

Add these secrets to the GitHub `staging` environment:

| Secret | Purpose |
|---|---|
| `VPS_HOST` | VPS hostname or IP |
| `VPS_USER` | SSH user allowed to deploy |
| `VPS_SSH_PORT` | SSH port, usually `22` |
| `VPS_SSH_KEY` | Private deploy key for the VPS user |
| `VPS_SSH_KNOWN_HOSTS` | Pinned SSH host key line for the VPS |
| `VPS_DEPLOY_PATH` | Deploy checkout path, for example `/srv/telegram-outreach/deploy` |

Generate the known-hosts value from a trusted machine:

```bash
ssh-keyscan -p 22 <vps-host>
```

After these secrets are configured, pushes to `main` run CI first. A successful CI run then deploys
that exact commit to the staging VPS. The deploy job uses strict SSH host-key checking and never
receives app runtime secrets.

## Coding Agents on the VPS

Agents should never edit `/srv/telegram-outreach/deploy`.

Use the agent workspace:

```bash
cd /srv/telegram-outreach/agent-work
git fetch origin
git checkout -B agent/my-change origin/main
# edit, test, commit
git push -u origin agent/my-change
```

Agents should commit and push after every completed change slice that modifies the wiki or codebase.
Before staging, inspect `git status` and commit only the intended files for that slice. Use
`git ci "message"` only in a clean branch with no unrelated dirty work, because it stages with
`git add -A`.

Merge the branch into `main` only after CI passes. Production follows `main`; agent work stays
isolated until merged.
