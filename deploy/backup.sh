#!/usr/bin/env bash
#
# Nightly logical backup of the MatchLambda Postgres database.
#
# The database is the only part of this stack that cannot be rebuilt from git —
# the application, the migrations and the frontend all can. A free-tier host can
# also be reclaimed for being idle, so keep a copy somewhere else.
#
#   crontab -e
#   23 3 * * *  /opt/matchlambda/deploy/backup.sh >> /var/log/matchlambda-backup.log 2>&1
#
# Off-host copy: install rclone, configure a remote (Cloudflare R2, Backblaze
# B2, S3, ...), then set R2_REMOTE in .env. Without it the script keeps local
# copies only, which does NOT survive losing the host and says so on stderr.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

COMPOSE_FILE=docker-compose.prod.yml
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_KEEP="${BACKUP_KEEP:-7}"
R2_REMOTE="${R2_REMOTE:-}"

: "${POSTGRES_USER:?POSTGRES_USER is not set (looked in the environment and .env)}"
: "${POSTGRES_DB:?POSTGRES_DB is not set (looked in the environment and .env)}"

mkdir -p "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/${POSTGRES_DB}_${stamp}.sql.gz"

# -T gives up the TTY so this works from cron. --clean --if-exists makes the
# dump restorable over an existing database without dropping it first.
docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  | gzip -9 > "$target"

echo "[backup] wrote $target ($(du -h "$target" | cut -f1))"

# Keep the newest BACKUP_KEEP local dumps.
ls -1t "$BACKUP_DIR"/"${POSTGRES_DB}"_*.sql.gz 2>/dev/null \
  | tail -n "+$((BACKUP_KEEP + 1))" \
  | while read -r old; do
      rm -f "$old"
      echo "[backup] pruned $old"
    done

if [ -z "$R2_REMOTE" ]; then
  echo "[backup] WARNING: R2_REMOTE is unset — this copy is lost with the host" >&2
  exit 0
fi

if ! command -v rclone >/dev/null 2>&1; then
  echo "[backup] R2_REMOTE is set but rclone is not installed; kept the local copy only" >&2
  exit 1
fi

rclone copy "$target" "$R2_REMOTE"
echo "[backup] uploaded to $R2_REMOTE"

# Mirror the retention window remotely. A missing remote path is not fatal.
rclone delete --min-age "${BACKUP_KEEP}d" "$R2_REMOTE" 2>/dev/null || true
