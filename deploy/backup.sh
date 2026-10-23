#!/usr/bin/env bash
# Nightly backup of the database and uploaded files into deploy/backups/. Keeps 14 days.
# Cron (as the user that runs Docker): 30 3 * * * /path/to/brand-studio/deploy/backup.sh
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
stamp=$(date +%Y-%m-%d)
docker compose exec -T db pg_dump -U brand -d brand --clean --if-exists \
  | gzip > "backups/db-$stamp.sql.gz.part"
docker compose exec -T api tar -czf - -C /data storage > "backups/files-$stamp.tar.gz.part"
mv "backups/db-$stamp.sql.gz.part" "backups/db-$stamp.sql.gz"
mv "backups/files-$stamp.tar.gz.part" "backups/files-$stamp.tar.gz"
find backups -name '*.gz' -mtime +14 -delete
echo "backup ok: $stamp"
