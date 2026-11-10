# Reed's site (production since 9 Nov 2026; formerly the test site, Brand Studio Next)

**This is Reed's production site: real providers, real money, Reed's real work.** Agents never
experiment on it: never switch it to the stand-ins, never reset it or remove its volumes, and
never run a paid test here without Reed's OK (logged in ops/SPEND.md). Every merge to `next`
deploys straight to it, so merges are bundled into Reed's windows until a stand-in-only preview
exists for agents to test on.

The `next` branch, on the server as its own Docker Compose project (`brand-studio-next`): its own
database, files, images and worker lanes. The old production site (`main`, project
`brand-studio`) is stopped and kept as a snapshot (`deploy/README.md`); don't touch it.

**Address:** **https://thisisatestingenv.online** (also the server's address on port 8443,
`https://srv2091584.hstgr.cloud:8443`). The old site's Caddy container is still the front door: it
holds ports 80, 443 and 8443 and forwards here over a private Docker network,
`brand-studio-edge`. It stays running until a separate front door replaces it.

**Deploys:** every push to `next` runs `.github/workflows/deploy-next.yml` (checks first, then
`deploy/next/remote-deploy.sh` over SSH). Safe to re-run. A deploy lets each worker finish the job
in hand (up to 10 minutes; the Claude worker up to 30, for a long video's shots), then restarts
in about a minute. **It refuses to deploy** (nothing
changes) unless repo variable `NEXT_FAKE_PROVIDERS` is `false`.

**Backups:** every night at 3:30 (server time) the database and all files are saved to
`~/brand-studio-next/deploy/backups/` (`deploy/backup.sh`, installed by each deploy; log in
`backups/backup.log`). The database is `backups/db-DATE.sql.gz`. The files are `backups/files/DATE/`,
a plain folder you can browse, with every file as it was that night; files unchanged since the
night before are shared between nights (hard links), so a night costs only what's new or changed
(about 13 GB in all for 13 GB of files, plus whatever changes over the 14 days). Kept 14 days
(`KEEP_DAYS=14` in the cron line), and the newest 3 of each are never deleted. If copying the
night's changes would leave under 15 GB free, that night saves only the database and writes a
WARNING line in the log. Each night ends with one line in the log, `backup DATE: ok` (or `WARNING`
or `FAILED`) with the MB copied and the nights kept; every deploy prints the newest one. The copy
runs at the lowest CPU and disk priority, without network, so it doesn't slow the site. Each
deploy also builds its small image (`brand-studio-backup:1`), which the restore below uses. A night that fails halfway leaves `backups/files/.part`, which the next
night finishes. The old full copies (`backups/files-DATE.tar.gz`, until 10 Nov) age out after 14
days. They don't survive losing the server: now and then copy that folder elsewhere with
`rsync -aH` (plain `cp` or `scp` stores every night in full). **Restore** (Web console, replace the
date; this replaces what's on the site now):
```
cd ~/brand-studio-next/deploy
c="docker compose -p brand-studio-next -f docker-compose.yml -f next/compose.yml"
$c stop api worker claude-worker reel-worker
gunzip -c backups/db-2026-11-10.sql.gz | $c exec -T db psql -q -U brand -d brand
# files too, if needed (puts back that night's files; files added since stay):
docker run --rm -v brand-studio-next_files:/data/storage -v "$PWD/backups/files/2026-11-10:/from:ro" brand-studio-backup:1 rsync -a --numeric-ids /from/ /data/storage/
# (an old full copy instead: $c run --rm --no-deps -T api tar -xzf - -C /data < backups/files-2026-11-09.tar.gz)
$c up -d --no-build
```
One file only: find it under `backups/files/DATE/` (same folders as on the site) and copy it back
the same way, with its path after `/from/` and `/data/storage/`.

**One-time setup (done; kept for reference)**
1. The front door's side (merged to `main`): `deploy/Caddyfile` answers on 8443,
   `deploy/docker-compose.yml` publishes 8443 and joins `brand-studio-edge`.
2. Hostinger firewall: if it has rules, allow TCP 8443 (VPS → Security → Firewall).
3. Reed's owner account, by a one-time invite link. In the Hostinger Web console, paste
   (with Reed's email):
   ```
   cd ~/brand-studio-next/deploy && docker compose -p brand-studio-next -f docker-compose.yml -f next/compose.yml exec -T api python -m app.owner_invite reed@example.com
   ```
   It prints the link (valid 7 days). Running it again replaces the link. The first run also
   makes the workspace and the launch brands (fomo, Iron Paws: kits and screens from the repo's
   `assets/brands`, never the old site's data). Nobody else ever sees the link.

**Settings** (repo variables, Settings → Secrets and variables → Actions → Variables; they take
effect on the next deploy). These are Reed's permanent production settings, not a test:
- `NEXT_FAKE_PROVIDERS=false`: real providers. **Never set it to `true` or delete it**: the
  deploy refuses, and if it didn't, Reed's queued real work would come out as grey stand-ins.
- `NEXT_GENERATION_ENABLED=true`: paid jobs run. `NEXT_OWNER_UNCAPPED=true`: no money holds on
  Reed's own work (editors are held as before).
- `NEXT_REAL_BUDGET_USD` (dollars, effectively no cap at 100000) from `NEXT_REAL_BUDGET_SINCE` (an
  ISO time): every paid call counts against it. Don't set it to 0: that refuses paid jobs that
  have no owner attached. Spent so far: the owner's `GET /api/credits/real-budget`.
- `NEXT_ITEM_CHECKS_PAID=true`: the take checks (eyes, screens, cast, words); self-approval, the
  director's redos and best take need them. `NEXT_ITEM_CHECK_SCOPE`: `key_takes`, `all_takes`
  (now) or `everything`.
- `NEXT_KIE_SUNO=true` with `NEXT_KIE_BUDGET_USD` (100000) and `NEXT_KIE_DELIVERY_HOSTS`: real songs.
- Off unless Reed asks: `NEXT_NARRATION_MUSIC_PAID` (a narration's music bed, with
  `NEXT_NARRATION_MUSIC_BUDGET_USD`) and `NEXT_SITE_READ_REAL` ("Import from website" reads the
  real site). The look and language sample switches only mattered with the stand-ins on.

Every real job writes usage rows (the Usage screen shows them). Agents' paid runs, only with
Reed's OK, also go in ops/SPEND.md.
