# Running Brand Studio on the VPS

Everything runs in Docker on one server: the database (Postgres), the app, the background
worker, and Caddy, which serves the website and gets the HTTPS certificate by itself.

GitHub deploys it: every merge to main runs all the checks, then logs in to the VPS over SSH and
runs `deploy/remote-deploy.sh`. The first run installs what's missing, downloads the code and
creates the settings file (the database password is made on the server and never leaves it).
Every run then rebuilds, waits for `https://<address>/api/health`, refreshes the launch brands'
screens and keeps the nightly backup switched on. If the site doesn't come up, the run fails red
in the repo's **Actions** tab with the server's last log lines.

## One-time setup (works from a phone browser)

1. **On Hostinger, open the VPS's Web console** (VPS → your server → Docker Manager or Overview →
   **Web console**) and paste:
   ```
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/deploy_key -q && cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys && base64 -w0 ~/.ssh/deploy_key; echo
   ```
   Copy the long line it prints. Then make a setup code with `openssl rand -hex 32` and copy that.
2. **In GitHub** (github.com in the browser, desktop site on): repo → Settings → Secrets and
   variables → Actions → **New repository secret**, one per line below.

   | Secret | What to paste |
   |---|---|
   | `VPS_HOST` | the VPS's IP address (Hostinger → VPS overview) |
   | `VPS_USER` | `root` |
   | `VPS_SSH_KEY` | the long line from step 1 |
   | `BS_SETUP_TOKEN` | the setup code from step 1 |
   | `REPLICATE_API_TOKEN` | your Replicate key (optional until generation is on) |
   | `STUDIO_ANTHROPIC_KEY` | your Claude key (optional until generation is on) |
   | `DOMAIN` | optional: your own address, e.g. `studio.yourdomain.com` (default: the VPS's own name, e.g. `srv123.hstgr.cloud`) |
   | `VPS_KNOWN_HOSTS` | optional, safer: the output of `ssh-keyscan <VPS IP>` from any computer |

   Then back in the Web console: `rm ~/.ssh/deploy_key`.
3. **Deploy:** repo → **Actions** → **deploy** → **Run workflow**. The first run takes about 10
   minutes; a green tick means it's live.
4. **Create the owner account** at `https://<address>/setup` with the setup code.
5. **Lock setup:** delete the `BS_SETUP_TOKEN` secret. The next deploy removes it from the server.

To use your own address later, add an `A` record for it pointing at the VPS's IP, set the
`DOMAIN` secret, and run the deploy again.

## Switching paid generation on or off

Repo → Settings → Secrets and variables → Actions → **Variables** → `BS_GENERATION_ENABLED` =
`true` or `false`, then run the deploy. It's off unless this says `true`.

## Backups

Every night at 3:30 (server time) `backup.sh` saves the database and all uploaded files to
`~/brand-studio/deploy/backups/` and keeps 14 days. Backups on the same server don't survive losing
the server: now and then copy that folder somewhere else (for example with `scp`).

**Restoring** a backup, in the Web console (replace the date):
```
cd ~/brand-studio/deploy
docker compose down
docker volume rm brand-studio_db brand-studio_files
docker compose up -d db && sleep 10
gunzip -c backups/db-2026-10-23.sql.gz | docker compose exec -T db psql -q -U brand -d brand
docker compose run --rm --no-deps -T api tar -xzf - -C /data < backups/files-2026-10-23.tar.gz
docker compose up -d
```

## When something's wrong

In the Web console, from `~/brand-studio/deploy`:
- See what's running: `docker compose ps`
- See recent messages: `docker compose logs --tail 50 api worker caddy`
- Restart everything: `docker compose restart`
- Deploy by hand (same as the workflow does): `git pull && docker compose up -d --build`

The database keeps the password it was first started with; the deploy reuses it from `.env`, so
never delete `deploy/.env` on the server.
