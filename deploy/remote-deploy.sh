#!/usr/bin/env bash
# Runs ON the VPS, piped in over SSH by .github/workflows/deploy.yml. Safe to run again.
# First run: installs what's missing, clones the repo, writes deploy/.env. Every run: updates
# the code, rebuilds, waits for /api/health, refreshes launch-brand screens, keeps backups on.
# Expects from the workflow: SETUP_TOKEN, REPLICATE, ANTHROPIC, GENERATION, DOMAIN_OVERRIDE.
set -euo pipefail

# Wrapped in a function so bash reads the whole script before any command can eat stdin.
main() {
  REPO=https://github.com/reedpafford/brand-studio.git
  APP="$HOME/brand-studio"

  command -v git >/dev/null || { apt-get update -qq && apt-get install -y -qq git; }
  command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh

  [ -d "$APP/.git" ] || git clone -q "$REPO" "$APP"
  cd "$APP"
  git fetch -q origin main && git reset -q --hard origin/main
  cd deploy

  # Settings. The database password is made here once and never leaves the server.
  old() { grep -E "^$1=" .env 2>/dev/null | cut -d= -f2- || true; }
  db_password=$(old POSTGRES_PASSWORD)
  [ -n "$db_password" ] || db_password=$(openssl rand -hex 24)
  domain=${DOMAIN_OVERRIDE:-$(old DOMAIN)}
  [ -n "$domain" ] || domain=$(hostname -f)
  umask 077
  {
    echo "DOMAIN=$domain"
    echo "POSTGRES_PASSWORD=$db_password"
    [ -z "$SETUP_TOKEN" ] || echo "BS_SETUP_TOKEN=$SETUP_TOKEN"
    echo "BS_GENERATION_ENABLED=${GENERATION:-false}"
    echo "REPLICATE_API_TOKEN=$REPLICATE"
    echo "STUDIO_ANTHROPIC_KEY=$ANTHROPIC"
  } > .env.new
  mv .env.new .env

  docker compose up -d --build --remove-orphans

  for _ in $(seq 1 60); do
    if curl -fsS --max-time 5 "https://$domain/api/health" >/dev/null; then
      echo "Live at https://$domain"
      # Launch brands' screens follow assets/brands/*/screens/screens.json (free, repeatable).
      if grep -q refresh ../server/app/seed.py; then
        docker compose exec -T api python -m app.seed refresh
      fi
      mkdir -p backups
      line="30 3 * * * $PWD/backup.sh >> $PWD/backups/backup.log 2>&1"
      (crontab -l 2>/dev/null | grep -v 'deploy/backup.sh' || true; echo "$line") | crontab -
      docker image prune -f >/dev/null
      exit 0
    fi
    sleep 5
  done
  echo "::error::https://$domain/api/health did not answer within 5 minutes."
  docker compose ps -a
  docker compose logs --tail 40 migrate api worker reel-worker caddy
  exit 1
}
main
