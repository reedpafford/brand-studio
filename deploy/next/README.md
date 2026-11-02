# Brand Studio Next (the test site)

The `next` branch, running on the live server as its own Docker Compose project
(`brand-studio-next`): its own database, files, images and worker lanes. Nothing is shared with
live. It runs on the free stand-ins (grey pictures, simple answers), so it never spends money.

**Address:** the live address on port 8443, e.g. `https://srv2091584.hstgr.cloud:8443`. Live's
Caddy answers there (it holds ports 80 and 443) and forwards to this stack over a private Docker
network, `brand-studio-edge`. If the test site is down, only port 8443 fails; live is unaffected.
It also answers at `https://thisisatestingenv.online` (port 443, for cloud sessions that only reach
443) once that name's DNS A record points at the server: the same site and accounts, signed in separately.

**Deploys:** every push to `next` runs `.github/workflows/deploy-next.yml` (checks first, then
`deploy/next/remote-deploy.sh` over SSH, with the live deploy's secrets). Safe to re-run.

**One-time setup**
1. Live's side (needs the Producer's OK, merged to `main`): `deploy/Caddyfile` answers on 8443,
   `deploy/docker-compose.yml` publishes 8443 and joins `brand-studio-edge`.
2. Hostinger firewall: if it has rules, allow TCP 8443 (VPS → Security → Firewall).
3. Reed's owner account, by a one-time invite link. In the Hostinger Web console, paste
   (with Reed's email):
   ```
   cd ~/brand-studio-next/deploy && docker compose -p brand-studio-next -f docker-compose.yml -f next/compose.yml exec -T api python -m app.owner_invite reed@example.com
   ```
   It prints the link (valid 7 days). Running it again replaces the link. The first run also
   makes the workspace and the launch brands (fomo, Iron Paws: kits and screens from the repo's
   `assets/brands`, never live data). Nobody else ever sees the link.

**A paid test** (only one Reed and the Producer approved, logged in ops/SPEND.md): repo variables
`NEXT_FAKE_PROVIDERS=false` and `NEXT_GENERATION_ENABLED=true`, run deploy-next, run the test,
then set `NEXT_FAKE_PROVIDERS` back to `true` and run deploy-next again. Every real call counts
against `NEXT_REAL_BUDGET_USD` (dollars) from `NEXT_REAL_BUDGET_SINCE` (an ISO time like
`2026-11-02T09:00:00Z`). Set both together; with either unset, nothing paid runs. A new budget
starts counting at its new start time. Past it, a press says "The test site's real-AI budget ($N) is used up. Nothing was
charged." and queued work isn't sent. Spent so far: the owner's `GET /api/credits/real-budget`,
or the worker's log lines "real budget: $X of $Y since …".

Other paid switches for a paid test, all off by default and all inside the same real budget
(they only matter with `NEXT_FAKE_PROVIDERS=false`):
- `NEXT_ITEM_CHECKS_PAID=true`: the take checks (eyes, screens, cast, words). Self-approval, the
  director's redos and best take need them. `NEXT_ITEM_CHECK_SCOPE` says how much they cover:
  `key_takes` (default), `all_takes` or `everything`.
- `NEXT_NARRATION_MUSIC_PAID=true` with `NEXT_NARRATION_MUSIC_BUDGET_USD`: a narration's music bed.
- `NEXT_SITE_READ_REAL=true`: "Import from website" reads the real site.

**Start over:** `docker compose -p brand-studio-next -f docker-compose.yml -f next/compose.yml down -v`
then run deploy-next. This wipes only the test site.
