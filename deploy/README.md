# Running Brand Studio on the VPS

Everything runs in Docker on one server: the database (Postgres), the app, the background
worker, and Caddy, which serves the website and gets the HTTPS certificate by itself.

## One-time setup

1. **Install Docker** on the VPS (Ubuntu):
   ```
   curl -fsSL https://get.docker.com | sh
   ```
   If you won't log in as root, also run `sudo usermod -aG docker $USER`, then log out and back in.

2. **Point a domain at the VPS.** At your domain provider, add an `A` record for the address you
   want (for example `studio.yourdomain.com`) pointing at the VPS's IP address. Ports 80 and 443
   must be open (Hostinger's firewall, and `ufw` if you use it).

3. **Get the code:**
   ```
   cd ~ && git clone https://github.com/reedpafford/brand-studio.git
   cd brand-studio/deploy
   ```

4. **Create the settings file** and fill it in:
   ```
   cp .env.example .env
   nano .env
   ```
   - `DOMAIN`: the address from step 2.
   - `POSTGRES_PASSWORD`: paste the output of `openssl rand -hex 24`.
   - `BS_SETUP_TOKEN`: paste the output of `openssl rand -hex 32`.
   - `REPLICATE_API_TOKEN`, `STUDIO_ANTHROPIC_KEY`: your keys.
   - Leave `BS_GENERATION_ENABLED=false` until you want paid generation on.

   This file holds your keys. It stays on the server only; never paste it anywhere.
   The app refuses to start while `change-me` is still in there, and says which line to fix.
   The database keeps the password it was first started with. If you need to change it before
   any real work exists, run `docker compose down -v` (this wipes everything) and start again.

5. **Start it:**
   ```
   docker compose up -d
   ```
   The first start takes a few minutes. Then open `https://<your domain>`.

6. **Create the owner account.** Open `https://<your domain>/setup` and enter the
   `BS_SETUP_TOKEN` from your `.env` along with your name, email and password.

7. **Remove the setup code** so nobody else can use it: delete the `BS_SETUP_TOKEN` line from
   `.env`, then run `docker compose up -d` again.

## Updating

From `~/brand-studio/deploy`:
```
git pull && docker compose up -d --build
```
This also updates the database automatically. Check it's up: `curl https://<your domain>/api/health`
should say `{"status":"ok"}`.

## Switching paid generation on or off

Edit `BS_GENERATION_ENABLED` in `.env` (`true` or `false`), then `docker compose up -d`.

## Nightly backups

`backup.sh` saves the database and all uploaded files to `deploy/backups/`, keeping 14 days.
Turn it on once with `crontab -e` and add this line (runs at 3:30 every night):
```
30 3 * * * $HOME/brand-studio/deploy/backup.sh >> $HOME/brand-studio/deploy/backups/backup.log 2>&1
```
Backups on the same server don't survive losing the server: now and then, copy the
`backups` folder somewhere else (for example with `scp` to your computer).

**Restoring** a backup (replace the date):
```
docker compose down
docker volume rm brand-studio_db brand-studio_files
docker compose up -d db && sleep 10
gunzip -c backups/db-2026-10-23.sql.gz | docker compose exec -T db psql -q -U brand -d brand
docker compose run --rm --no-deps -T api tar -xzf - -C /data < backups/files-2026-10-23.tar.gz
docker compose up -d
```

## When something's wrong

- See what's running: `docker compose ps`
- See recent messages: `docker compose logs --tail 50 api worker caddy`
- Restart everything: `docker compose restart`

## Automatic deploys (optional, off)

`docs/deploy/auto-deploy.md` has a ready workflow that deploys on every merge to main, and the
GitHub secrets it needs. It isn't switched on; Reed decides.
