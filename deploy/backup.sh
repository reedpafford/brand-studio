#!/usr/bin/env bash
# Nightly backup into deploy/backups/: the database as db-DATE.sql.gz, and the uploaded files as
# files/DATE/, a plain browsable copy of the files volume. Each night's copy hard-links the files
# unchanged since the night before, so it costs only what's new or changed. Keeps KEEP_DAYS days
# (default 14), but never deletes the newest 3 of each kind. The files are skipped (database still
# saved) when copying the changes would leave under MIN_FREE_GB (default 15) free, so a backup never
# fills the disk. Ends with one summary line, "backup DATE: ok|WARNING|FAILED ...". Cron, installed
# by deploy/next/remote-deploy.sh for Reed's site: 30 3 * * * cd ~/brand-studio-next/deploy &&
#   KEEP_DAYS=14 COMPOSE_PROJECT_NAME=brand-studio-next COMPOSE_FILE=docker-compose.yml:next/compose.yml ./backup.sh
# "./backup.sh image" only builds the copying image (each deploy does, so restores have it).
set -euo pipefail
cd "$(dirname "$0")"

# The files are copied by a throwaway container: rsync on Alpine, at the lowest CPU and disk
# priority (ionice where the kernel allows it) so a big first copy can't slow the site.
img=brand-studio-backup:1
need_image() {
  docker image inspect "$img" >/dev/null 2>&1 || docker build -q -t "$img" - >/dev/null <<'EOF'
FROM alpine:3.20
RUN apk add --no-cache rsync \
 && printf '#!/bin/sh\nif ionice -c3 true 2>/dev/null; then set -- ionice -c3 "$@"; fi\nexec nice -n 19 "$@"\n' > /low \
 && chmod +x /low
ENTRYPOINT ["/low"]
EOF
}
if [ "${1:-}" = image ]; then need_image; exit; fi

mkdir -p backups/files
keep=${KEEP_DAYS:-14}
stamp=$(date +%Y-%m-%d)
cutoff=$(date -d "$keep days ago" +%Y-%m-%d 2>/dev/null || date -v-"$keep"d +%Y-%m-%d)
status=ok db="not saved" files="not copied"
summary() {
  local rc=$? n
  rm -f backups/*.part  # a half-written dump never stays behind to fill the disk
  [ "$rc" -eq 0 ] || status="FAILED (exit $rc)"
  n=$(find backups/files -maxdepth 1 -name '????-??-??' | wc -l | tr -d ' ')
  echo "backup $stamp: $status. Database $db. Files $files. $n nights of files kept."
}
trap summary EXIT

# Old ones first, to make room. Arguments: one kind's backups, oldest first (dates in the names
# sort them). The newest 3 always stay, so failing nights can't age out the last good backups.
prune() {
  [ "$#" -gt 3 ] || return 0
  local f
  for f in "${@:1:$#-3}"; do find "$f" -mtime +"$keep" -delete; done
}
prune backups/db-*.sql.gz

docker compose exec -T db pg_dump -U brand -d brand --clean --if-exists \
  | gzip > "backups/db-$stamp.sql.gz.part"
mv "backups/db-$stamp.sql.gz.part" "backups/db-$stamp.sql.gz"
db=saved

# The container reads the volume read-only, has no network, and writes as root into
# backups/files/, so it also does the deleting and renaming there.
vol=$(docker volume ls -q --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME:?}" \
  --filter label=com.docker.compose.volume=files)
[ -n "$vol" ] || { files="not copied: no files volume for $COMPOSE_PROJECT_NAME"; exit 1; }
need_image
box() { docker run --rm --network none -v "$vol:/data/storage:ro" -v "$PWD/backups/files:/backups" "$img" "$@"; }

# Old nights go by the date in the name (a copy keeps the files' own times, not the night's).
prune_nights() {
  [ "$#" -gt 3 ] || return 0
  local d old=()
  for d in "${@:1:$#-3}"; do [[ "${d##*/}" < "$cutoff" ]] && old+=("/backups/${d##*/}"); done
  [ "${#old[@]}" -eq 0 ] || box rm -rf "${old[@]}"
}
prune_nights backups/files/????-??-??
prev=""  # the newest copy (tonight's, on a re-run): unchanged files are linked to it
for d in backups/files/????-??-??; do [ ! -d "$d" ] || prev=${d##*/}; done
# The full tarballs from before the nightly copies age out too, once a copy exists.
[ -z "$prev" ] || find backups -maxdepth 1 -name 'files-*.tar.gz' -mtime +"$keep" -delete

# Written into .part (kept after a failed night: the next run picks it up), renamed when complete.
# Exit code 24 only means a file was deleted on the site mid-copy.
copy() { box rsync -a --delete --numeric-ids ${prev:+"--link-dest=/backups/$prev"} "$@" /data/storage/ /backups/.part/; }
stats=$(copy --dry-run --stats) || [ $? -eq 24 ]
delta_kb=$(( $(awk -F: '/Total transferred file size/ {gsub(/[^0-9]/, "", $2); print $2 + 0}' <<< "$stats") / 1024 ))
free_kb=$(df -Pk backups | awk 'NR == 2 {print $4}')
need_kb=$(( delta_kb + ${MIN_FREE_GB:-15} * 1048576 ))
if [ "$free_kb" -lt "$need_kb" ]; then
  status=WARNING files="skipped: only $(( free_kb / 1048576 )) GB free, needs $(( need_kb / 1048576 )) GB"
  exit 0
fi
copy || [ $? -eq 24 ]
box rm -rf "/backups/$stamp"  # a re-run tonight: .part has everything, linked or copied
box mv /backups/.part "/backups/$stamp"
files="copied: $(( delta_kb / 1024 )) MB new or changed"
