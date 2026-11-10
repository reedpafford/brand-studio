#!/usr/bin/env bash
# Runs ON the VPS, piped in over SSH by .github/workflows/deploy.yml (every push to main). Safe to
# run again. Since 9 Nov the old production site is retired (Reed): this keeps a snapshot of it and
# keeps it stopped. Its web server (caddy) keeps running: it is also the front door of Reed's site
# (thisisatestingenv.online and port 8443). Nothing of the old site is moved, rebuilt or deleted:
# only `stop` (never `down`, never a volume), and its checkout and deploy/.env are never changed.
# The settings deploy.yml still exports are ignored. Restore: deploy/README.md "Old production site".
set -euo pipefail

# Wrapped in a function so bash reads the whole script before any command can eat stdin.
main() {
  cd "$HOME/brand-studio/deploy"  # the old site's checkout (project brand-studio)
  SNAP="$HOME/old-production-snapshot"
  NEXT="$HOME/brand-studio-next/deploy"  # Reed's site (project brand-studio-next)
  REEDS_SITE=https://thisisatestingenv.online
  umask 077
  # Never at the same time as a deploy of Reed's site (deploy/next/remote-deploy.sh takes it too).
  exec 9>/tmp/brand-studio-deploy.lock
  flock -w 1200 9 || { echo "::error::Another deploy held the server for 20 minutes. Nothing was changed; run this again."; exit 1; }
  old() { docker compose -p brand-studio "$@"; }
  reeds() { (cd "$NEXT" && docker compose -p brand-studio-next -f docker-compose.yml -f next/compose.yml "$@"); }

  # 1. The snapshot, once: a fresh database dump, the settings file, the code commit, and the
  #    images tagged so no clean-up removes them. Its volumes stay exactly as they are.
  if [ ! -f "$SNAP/DONE" ]; then
    install -m 700 -d "$SNAP"
    old stop worker claude-worker reel-worker api  # a job in hand may finish (up to 10 min)
    git -C .. rev-parse HEAD > "$SNAP/code-commit.txt"
    install -m 600 .env "$SNAP/old-production.env"
    old exec -T db pg_dump -U brand -d brand --clean --if-exists | gzip > "$SNAP/old-production-db.sql.gz.part"
    mv "$SNAP/old-production-db.sql.gz.part" "$SNAP/old-production-db.sql.gz"
    docker tag brand-studio-server brand-studio-server:old-production
    docker tag brand-studio-web brand-studio-web:old-production
    { docker image ls brand-studio-server; docker image ls brand-studio-web; } > "$SNAP/images.txt"
    docker volume ls --filter label=com.docker.compose.project=brand-studio > "$SNAP/volumes.txt"
    ls -l backups/ > "$SNAP/nightly-backups.txt" 2>/dev/null || true
    date -u +%FT%TZ > "$SNAP/DONE"
    echo "Snapshot made in $SNAP."
  fi

  # 2. Stop everything of the old site but its web server (Reed's site's front door).
  old stop worker claude-worker reel-worker api db
  # If anything took the web server down with the rest, start that one container again directly
  # (plain docker: no Compose dependencies, so the old API stays stopped). Not once a separate
  # front door (project brand-studio-edge) holds the ports.
  caddy=$(docker ps -aq --filter label=com.docker.compose.project=brand-studio --filter label=com.docker.compose.service=caddy)
  if [ -z "$(docker ps -q --filter label=com.docker.compose.project=brand-studio-edge)" ]; then
    [ -n "$caddy" ] || { echo "::error::The old site's web server container is missing: Reed's site has no front door. See deploy/README.md."; exit 1; }
    [ "$(docker inspect -f '{{.State.Running}}' "$caddy")" = true ] || docker start "$caddy" >/dev/null
  fi

  # 3. The old nightly backup would only fail now; removing it also stops it pruning the old
  #    backups in ~/brand-studio/deploy/backups/ (kept for good). Reed's site's backup stays.
  (crontab -l 2>/dev/null | grep -vF "/brand-studio/deploy/backup.sh" || true) | crontab -

  # 4. A backup of Reed's site's database (read-only), into its own backups folder.
  mkdir -p "$NEXT/backups"
  dump="$NEXT/backups/db-$(date +%F).sql.gz"
  reeds exec -T db pg_dump -U brand -d brand --clean --if-exists | gzip > "$dump.part" \
    || { rm -f "$dump.part"; echo "::error::Couldn't back up Reed's site's database. The old site is stopped; run this again."; exit 1; }
  mv "$dump.part" "$dump"
  echo "Reed's site's database saved: $dump ($(du -h "$dump" | cut -f1))."

  # 5. Where things stand, then Reed's site must answer.
  old ps -a
  free -m || true
  df -h / || true
  docker system df -v 2>/dev/null | grep -E '^(VOLUME NAME|brand-studio)' || true
  for _ in $(seq 1 12); do
    if curl -fsS --max-time 10 "$REEDS_SITE/api/health" | grep -q '"status":"ok"'; then
      echo "Old production stopped (snapshot: $SNAP). Reed's site answers at $REEDS_SITE."
      exit 0
    fi
    sleep 5
  done
  echo "::error::Reed's site ($REEDS_SITE) doesn't answer. Check the old web server runs: docker start $caddy"
  docker ps -a --filter label=com.docker.compose.project=brand-studio-next
  exit 1
}
main
