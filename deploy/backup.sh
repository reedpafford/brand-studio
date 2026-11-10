#!/usr/bin/env bash
# Nightly backup of the database and uploaded files into deploy/backups/. Keeps KEEP_DAYS days
# (default 14). Cron (as the user that runs Docker), installed by deploy/next/remote-deploy.sh for
# Reed's site: 30 3 * * * cd ~/brand-studio-next/deploy && COMPOSE_PROJECT_NAME=brand-studio-next
#   COMPOSE_FILE=docker-compose.yml:next/compose.yml ./backup.sh
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
trap 'rm -f backups/*.part' EXIT  # a half-written backup never stays behind to fill the disk
find backups -name '*.gz' -mtime +"${KEEP_DAYS:-14}" -delete  # old ones first: room for tonight's
stamp=$(date +%Y-%m-%d)
docker compose exec -T db pg_dump -U brand -d brand --clean --if-exists \
  | gzip > "backups/db-$stamp.sql.gz.part"
docker compose exec -T api tar -czf - -C /data storage > "backups/files-$stamp.tar.gz.part"
mv "backups/db-$stamp.sql.gz.part" "backups/db-$stamp.sql.gz"
mv "backups/files-$stamp.tar.gz.part" "backups/files-$stamp.tar.gz"
echo "backup ok: $stamp"
