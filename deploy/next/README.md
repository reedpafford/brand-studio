# Brand Studio Next (the test site)

The `next` branch, running on the live server as its own Docker Compose project
(`brand-studio-next`): its own database, files, images and worker lanes. Nothing is shared with
live. It runs on the free stand-ins (grey pictures, simple answers), so it never spends money.

**Address:** the live address on port 8443, e.g. `https://srv2091584.hstgr.cloud:8443`. Live's
Caddy answers there (it holds ports 80 and 443) and forwards to this stack over a private Docker
network, `brand-studio-edge`. If the test site is down, only port 8443 fails; live is unaffected.
It also answers at `https://thisisatestingenv.tech` (port 443, for cloud sessions that only reach
443) once that name's DNS A record points at the server; same site, same sign-in.

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
then set `NEXT_FAKE_PROVIDERS` back to `true` and run deploy-next again.

**Start over:** `docker compose -p brand-studio-next -f docker-compose.yml -f next/compose.yml down -v`
then run deploy-next. This wipes only the test site.
