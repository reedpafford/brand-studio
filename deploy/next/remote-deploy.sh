#!/usr/bin/env bash
# Runs ON the VPS, piped in over SSH by .github/workflows/deploy-next.yml. Safe to run again.
# Brand Studio Next (the test site): its own checkout (~/brand-studio-next, branch next), its own
# Compose project (brand-studio-next) and deploy/.env. Never touches the live checkout or stack.
# Expects from the workflow: FAKE, GENERATION, REPLICATE, ANTHROPIC (keys only when FAKE=false),
# and KIE, KIE_BUDGET, KIE_HOSTS (the KIE key only while real songs are switched on).
set -euo pipefail

main() {
  REPO=https://github.com/reedpafford/brand-studio.git
  APP="$HOME/brand-studio-next"
  PORT=8443  # live's Caddy answers https on this port and forwards here (deploy/Caddyfile)

  command -v git >/dev/null || { apt-get update -qq && apt-get install -y -qq git; }
  command -v docker >/dev/null || { echo "::error::Docker is missing: deploy live first."; exit 1; }
  # `ports: !reset` in next/compose.yml needs Compose 2.24.4 or newer.
  version=$(docker compose version --short | sed 's/^v//')
  if [ "$(printf '%s\n2.24.4\n' "$version" | sort -V | head -1)" != 2.24.4 ]; then
    echo "::error::Docker Compose $version is too old (2.24.4 or newer)."; exit 1
  fi

  [ -d "$APP/.git" ] || git clone -q "$REPO" "$APP"
  cd "$APP"
  git fetch -q origin next && git reset -q --hard origin/next
  cd deploy

  # The same address as live (its .env says which), on port 8443.
  old() { grep -E "^$1=" "$2" 2>/dev/null | cut -d= -f2- || true; }
  domain=$(old DOMAIN "$HOME/brand-studio/deploy/.env")
  [ -n "$domain" ] || domain=$(hostname -f)
  db_password=$(old POSTGRES_PASSWORD .env)
  [ -n "$db_password" ] || db_password=$(openssl rand -hex 24)
  fake=${FAKE:-true}
  umask 077
  {
    echo "DOMAIN=$domain"
    echo "PUBLIC_ADDRESS=$domain:$PORT"
    echo "POSTGRES_PASSWORD=$db_password"
    # Free stand-ins unless the Producer turns them off for an approved paid test.
    if [ "$fake" = false ]; then
      echo "BS_FAKE_PROVIDERS=false"
      echo "BS_GENERATION_ENABLED=${GENERATION:-false}"
      echo "REPLICATE_API_TOKEN=$REPLICATE"
      echo "STUDIO_ANTHROPIC_KEY=$ANTHROPIC"
    elif [ -n "${KIE:-}" ]; then  # stand-ins, but real songs: the one paid service here
      echo "BS_FAKE_PROVIDERS=true"
      echo "BS_GENERATION_ENABLED=true"
    else
      echo "BS_FAKE_PROVIDERS=true"
      echo "BS_GENERATION_ENABLED=false"
    fi
    if [ -n "${KIE:-}" ]; then  # Suno through KIE, stopped at the test budget
      hosts=$(printf '%s' "${KIE_HOSTS:-}" | tr -d ' ' | sed 's/[^,][^,]*/"&"/g')
      echo "BS_KIE_SUNO=true"
      echo "KIE_API_KEY=$KIE"
      echo "BS_KIE_BUDGET_USD=${KIE_BUDGET:-0}"
      echo "BS_KIE_DELIVERY_HOSTS=[$hosts]"
    fi
  } > .env.new
  mv .env.new .env

  # One deploy at a time on this server: live and the test site take turns building.
  exec 9>/tmp/brand-studio-deploy.lock
  flock -w 1200 9 || { echo "::error::Another deploy held the server for 20 minutes. The test site was left as it was; run deploy-next again."; exit 1; }
  docker network inspect brand-studio-edge >/dev/null 2>&1 || docker network create brand-studio-edge >/dev/null
  compose() { docker compose -p brand-studio-next -f docker-compose.yml -f next/compose.yml "$@"; }
  docker run --rm -v "$PWD/next/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2 \
    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null \
    || { echo "::error::deploy/next/Caddyfile doesn't validate. The test site was left as it was."; exit 1; }
  compose up -d --build --remove-orphans

  for _ in $(seq 1 60); do
    if compose exec -T caddy wget -qO- http://localhost/api/health 2>/dev/null | grep -q '"status":"ok"'; then
      compose exec -T api python -m app.seed refresh
      docker image prune -f >/dev/null
      if curl -fsS --max-time 5 "https://$domain:$PORT/api/health" | grep -q '"status":"ok"'; then
        echo "Test site at https://$domain:$PORT"
      else
        echo "::warning::The test site runs, but https://$domain:$PORT doesn't answer yet: live's Caddy needs its port $PORT change (deploy/Caddyfile), and the VPS firewall must allow TCP $PORT."
      fi
      exit 0
    fi
    sleep 5
  done
  echo "::error::The test site's /api/health did not answer within 5 minutes."
  compose ps -a
  compose logs --tail 40 migrate api worker claude-worker reel-worker caddy
  exit 1
}
main
