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
/srv/tg-outreach/staging            # reset-only staging checkout
/srv/tg-outreach/production         # reserved future production checkout
/srv/tg-outreach/agent-worktrees    # branch-based coding-agent worktrees
/srv/tg-outreach/AGENT_CONTEXT.md   # redacted VPS map for agents
/srv/tg-outreach/bin                # non-secret status/log/deploy helpers
```

Staging deployment always resets the target checkout to the selected ref or commit, builds the app
images, runs Alembic migrations, and restarts Docker Compose. Coding agents must work on branches in a
separate worktree, then push those branches to GitHub for CI and review.

## First VPS Setup

On the VPS:

```bash
sudo mkdir -p /srv/tg-outreach
sudo chown deploy:tg-outreach-deploy /srv/tg-outreach
sudo chmod 775 /srv/tg-outreach
cd /srv/tg-outreach
sudo -u deploy git clone git@github.com:<owner>/<repo>.git staging
```

Create `/etc/tg-outreach/staging.env`, then symlink it from the staging checkout as `.env`.

Install the redacted VPS context and helper commands from a checkout:

```bash
cd /srv/tg-outreach/staging
bash scripts/vps-install-agent-ops.sh
```

Agent-safe diagnostics:

```bash
/srv/tg-outreach/bin/tg-outreach-status staging
/srv/tg-outreach/bin/tg-outreach-logs staging api
```

If agent users do not have Docker access, install narrow sudoers rules and run diagnostics as
`deploy`:

```bash
sudo -u deploy /srv/tg-outreach/bin/tg-outreach-status staging
sudo -u deploy /srv/tg-outreach/bin/tg-outreach-logs staging api
```

Manual deploy:

```bash
sudo -u deploy /srv/tg-outreach/bin/tg-outreach-deploy staging origin/main
```

## GitHub Secrets for Staging Deploy

Add these secrets to the GitHub `staging` environment:

| Secret | Purpose |
|---|---|
| `VPS_HOST` | VPS hostname or IP |
| `VPS_USER` | SSH user allowed to deploy |
| `VPS_SSH_PORT` | SSH port, usually `22` |
| `VPS_SSH_KEY` | Private deploy key for the VPS user |
| `VPS_SSH_KNOWN_HOSTS` | Pinned SSH host key line for the VPS |
| `VPS_DEPLOY_PATH` | Deploy checkout path, for example `/srv/tg-outreach/staging` |

Generate the known-hosts value from a trusted machine:

```bash
ssh-keyscan -p 22 <vps-host>
```

After these secrets are configured, pushes to `main` run CI first. A successful CI run deploys that
exact commit to the staging VPS. Manual workflow dispatch can also deploy staging. The deploy job
uses strict SSH host-key checking and never receives app runtime secrets.

## Coding Agents on the VPS

Agents should never edit `/srv/tg-outreach/staging` or `/srv/tg-outreach/production`.

Start by reading the redacted VPS map:

```bash
cat /srv/tg-outreach/AGENT_CONTEXT.md
```

Use the agent workspace:

```bash
cd /srv/tg-outreach/agent-worktrees
git fetch origin
git checkout -B agent/my-change origin/main
# edit, test, commit
git push -u origin agent/my-change
```

Agents should commit and push after every completed change slice that modifies the wiki or codebase.
Before staging, inspect `git status` and commit only the intended files for that slice. Use
`git ci "message"` only in a clean branch with no unrelated dirty work, because it stages with
`git add -A`.

Merge the branch into `main` only after CI passes. Staging follows `main`; agent work stays isolated
until merged.
