#!/usr/bin/env bash
# Nightly backup of the database and uploaded files into deploy/backups/. Keeps KEEP_DAYS days
# (default 14), but never deletes the newest 3 of each kind. The files are skipped (database
# still saved) when the disk has under MIN_FREE_GB (default 15) or twice the last files backup
# free, so a backup never fills the disk. Cron, installed by deploy/next/remote-deploy.sh for
# Reed's site: 30 3 * * * cd ~/brand-studio-next/deploy && KEEP_DAYS=14
#   COMPOSE_PROJECT_NAME=brand-studio-next COMPOSE_FILE=docker-compose.yml:next/compose.yml ./backup.sh
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
trap 'rm -f backups/*.part' EXIT  # a half-written backup never stays behind to fill the disk
keep=${KEEP_DAYS:-14}

# Old ones first, to make room. Arguments: one kind's files, oldest first (dates in the names sort
# them). The newest 3 always stay, so failing nights can't age out the last good backups.
prune() {
  [ "$#" -gt 3 ] || return 0
  local f
  for f in "${@:1:$#-3}"; do find "$f" -mtime +"$keep" -delete; done
}
prune backups/db-*.sql.gz
prune backups/files-*.tar.gz

stamp=$(date +%Y-%m-%d)
docker compose exec -T db pg_dump -U brand -d brand --clean --if-exists \
  | gzip > "backups/db-$stamp.sql.gz.part"
mv "backups/db-$stamp.sql.gz.part" "backups/db-$stamp.sql.gz"

free_kb=$(df -Pk backups | awk 'NR == 2 {print $4}')
need_kb=$(( ${MIN_FREE_GB:-15} * 1024 * 1024 ))
last=$(find backups -name 'files-*.tar.gz' | sort | tail -1)
if [ -n "$last" ]; then
  last_kb=$(( $(wc -c < "$last") / 1024 ))
  [ $(( last_kb * 2 )) -le "$need_kb" ] || need_kb=$(( last_kb * 2 ))
fi
if [ "$free_kb" -lt "$need_kb" ]; then
  echo "WARNING $stamp: files not backed up, only $(( free_kb / 1048576 )) GB free (needs $(( need_kb / 1048576 )) GB). Database saved."
  exit 0
fi
docker compose exec -T api tar -czf - -C /data storage > "backups/files-$stamp.tar.gz.part"
mv "backups/files-$stamp.tar.gz.part" "backups/files-$stamp.tar.gz"
echo "backup ok: $stamp"
